import sys
import os
import logging
import tempfile
import pathlib

# 1. 最优先配置日志，确保任何启动错误都能被记录
log_file_path = os.path.join(tempfile.gettempdir(), "monobuck_audio_service.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file_path, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
logger.info(f"日志文件路径: {log_file_path}")
logger.info("正在初始化 Python 服务...")

# 2. Windows 下 PyInstaller 打包多进程必须调用 (放在 import 之前)
import multiprocessing
multiprocessing.freeze_support()

try:
    import asyncio
    import websockets
    import json
    import uuid
    import queue
    from datetime import datetime
    import time

    sys.path.insert(0, str(pathlib.Path(__file__).parent.resolve()))

    logger.info("正在导入核心模块...")
    from core.asr_service import ASRService
    from core.text_service import TextService
    logger.info("核心模块导入成功")

except Exception as e:
    logger.critical(f"启动期间发生严重错误 (Import/Init): {e}", exc_info=True)
    sys.exit(1)



"""注意：Python 侧不再负责音频文件物理持久化。

原先这里会在 `mono_core/audio_files/` 下保存 .raw/.wav 文件，
现在所有录音与会话持久化已经迁移到 Rust/Tauri 端。
Python 仅做流式 ASR/文本处理，不落盘音频。
"""

# 连接管理
class ConnectionManager:
    def __init__(self):
        self.active_connections = {}
        self.audio_buffers = {}
        self.audio_queues = {}
        self.stop_flags = {}
    
    def add_connection(self, websocket, client_id):
        #这里的client_id 正好对应客户端唯一的id，后续应该为客户端每个用户创建唯一的id
        self.active_connections[client_id] = websocket
        self.audio_buffers[client_id] = bytearray()
        self.audio_queues[client_id] = queue.Queue()
        self.stop_flags[client_id] = asyncio.Event()
        
        # Python 端不再负责音频文件命名与保存，返回占位信息
        filename = None
        file_path = None
        return file_path, filename
    
    def remove_connection(self, client_id):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        if client_id in self.audio_buffers:
            del self.audio_buffers[client_id]
        if client_id in self.audio_queues:
            del self.audio_queues[client_id]
        if client_id in self.stop_flags:
            del self.stop_flags[client_id]
    
    def add_audio_data(self, client_id, data):
        if client_id in self.audio_buffers:
            self.audio_buffers[client_id].extend(data)
        # 推入队列供 ASR 消费
        if client_id in self.audio_queues:
            try:
                self.audio_queues[client_id].put_nowait(data)
            except Exception:
                pass
    
    def get_audio_data(self, client_id):
        if client_id in self.audio_buffers:
            return bytes(self.audio_buffers[client_id])
        return None
    
    def get_audio_queue(self, client_id):
        return self.audio_queues.get(client_id)

    def get_stop_event(self, client_id):
        return self.stop_flags.get(client_id)



    # Python 侧不再提供 save_audio_to_raw/save_audio_to_wav，
    # 仅通过内存中的 audio_buffers 供 ASR 流式消费。
    
    def get_active_connections_count(self):
        """
        获取当前活跃连接数
        """
        return len(self.active_connections)
    
    # get_storage_statistics / clean_old_files 与物理文件无关的统计也一并移除，
    # 如需磁盘统计应改为由 Rust 侧 records 目录负责。


# 创建连接管理器与全局服务实例占位
manager = ConnectionManager()
asr: ASRService | None = None
text_service: TextService | None = None


# WebSocket处理函数
async def handle_connection(websocket, path):
    # 从路径中提取client_id
    # 路径格式: /ws/audio/{client_id}
    print(f"进入handle_connection...")
    try:
        parts = path.strip('/').split('/')
        if len(parts) >= 3 and parts[0] == 'ws' and parts[1] == 'audio':
            client_id = parts[2]
        else:
            # 如果路径格式不正确，生成一个新的client_id
            client_id = f"client_{uuid.uuid4().hex[:8]}"
        
        logger.info(f"客户端连接请求: {client_id}, 路径: {path}")
        print(f'客户端连接请求：{client_id}，路径：{path}',flush=True)
        
        # 添加连接
        file_path, filename = manager.add_connection(websocket, client_id)
        logger.info(f"客户端 {client_id} 已连接，音频文件将保存至: {file_path}")
        
        # 发送连接成功消息
        await websocket.send(json.dumps({
            "status": "connected",
            "message": "WebSocket连接已建立",
            "client_id": client_id,
            "filename": filename
        }))
        
        # 接收数据的累计大小
        total_bytes_received = 0

        # 启动 ASR 线程
        result_queue = queue.Queue()
        session_text_list = [] # 存储当前会话的所有识别结果
        import threading
        
        def run_asr_worker():
            global asr
            input_queue = manager.get_audio_queue(client_id)
            stop_event = manager.get_stop_event(client_id)
            if input_queue is None or stop_event is None:
                return

            def queue_iter():
                while True:
                    if stop_event.is_set() and input_queue.empty():
                        break
                    try:
                        # 阻塞式获取，带超时
                        item = input_queue.get(timeout=0.1)
                        if item == b"__STOP__": # 结束标记
                             break
                        if isinstance(item, (bytes, bytearray)) and len(item) > 0:
                            yield bytes(item)
                    except queue.Empty:
                        continue
                    except Exception:
                        break
            
            try:
                # 循环处理多个会话
                while not stop_event.is_set():
                    # 等待第一个数据包或停止信号
                    try:
                        # 预读一个，如果不是 STOP 则放回或开始 generator
                        # 这里简化：直接进入 transcribe_stream，它会阻塞在 queue_iter
                        # 但 queue_iter 需要能区分 session。
                        # 简单方案：queue_iter 遇到 __STOP__ 退出，transcribe_stream 结束。
                        # 外层循环再次调用 transcribe_stream。
                        
                        # 检查队列是否为空，避免空转
                        if input_queue.empty():
                            time.sleep(0.05)
                            continue
                            
                        print("ASR Worker: 开始新一轮识别会话")
                        if asr is None:
                            logger.error("ASRService 未初始化")
                            break
                        last_part = None
                        for part in asr.transcribe_stream(queue_iter()):
                            print(f'识别中间结果: {part}')
                            if part.get("is_final"):
                                result_queue.put(part)
                                last_part = None
                            else:
                                last_part = part
                        
                        if last_part and last_part.get("text"):
                            print(f"ASR Worker: 会话结束，强制提交最后未完成片段: {last_part['text']}")
                            last_part["is_final"] = True
                            result_queue.put(last_part)
                        
                        # 发送会话结束标记
                        result_queue.put({"status": "session_end"})
                            
                        print("ASR Worker: 本轮识别会话结束")
                        
                    except Exception as e:
                        logger.error(f"ASR线程出错: {e}", exc_info=True)
                        time.sleep(1) # 出错后冷却
                        
            except Exception as e:
                logger.error(f"ASR Worker 致命错误: {e}", exc_info=True)

        asr_thread = threading.Thread(target=run_asr_worker, daemon=True)
        asr_thread.start()

        # 启动结果发送任务
        async def asr_consumer():
            while True:
                try:
                    try:
                        part = result_queue.get_nowait()
                        
                        # 检查是否是会话结束标记
                        if part.get("status") == "session_end":
                            # 触发 Refine 逻辑
                            raw_text = "。".join(session_text_list)
                            session_text_list.clear() # 清空，准备下一次
                            
                            if raw_text:
                                logger.info(f"开始 Refine, 原始文本: {raw_text}")
                                try:
                                    # 在线程池中运行 Refine，避免阻塞事件循环
                                    refined_text = await asyncio.to_thread(text_service.refine, raw_text)
                                    logger.info(f"Refine 完成: {refined_text}")
                                    
                                    await websocket.send(json.dumps({
                                        "status": "final_result",
                                        "raw_text": raw_text,
                                        "refined_text": refined_text
                                    }))
                                except Exception as e:
                                    logger.error(f"Refine 失败: {e}")
                                    await websocket.send(json.dumps({
                                        "status": "error",
                                        "message": f"Refine 失败: {str(e)}"
                                    }))
                            else:
                                logger.info("没有识别到文本，跳过 Refine")
                            continue

                        text = part.get("text", "")
                        is_final = part.get("is_final", False)
                        
                        # 只有当 is_final 为 True 时，才将文本添加到 session_text_list
                        if is_final:
                            session_text_list.append(text)
                        
                        await websocket.send(json.dumps({
                            "status": "recognition_result",
                            "text": text,
                            "is_final": is_final
                        }))
                    except queue.Empty:
                        if not asr_thread.is_alive() and result_queue.empty():
                            break
                        await asyncio.sleep(0.05)
                except Exception as e:
                    logger.error(f"发送结果出错: {e}")
                    break

        consumer_task = asyncio.create_task(asr_consumer())
        
        

        # 处理接收到的消息
        while True:
            try:
                # 接收二进制数据
                data = await websocket.recv()
                
                # 检查数据类型
                if isinstance(data, bytes):
                    # 过滤空分片与非 PCM16 合法性（最基本：非空）
                    if len(data) == 0:
                        # 跳过空分片，避免 ASR 端无效音频错误
                        continue
                    # 将音频数据放入队列
                    manager.add_audio_data(client_id, data)
                    total_bytes_received += len(data)
                    # print(f'收到音频数据: {type(data)}{len(data)} {data[:10]}')
                    
                    # 每接收一定量的数据发送状态更新
                    if total_bytes_received % 10240 < len(data):
                        await websocket.send(json.dumps({
                            "status": "receiving",
                            "bytes_received": len(data),
                            "total_bytes": total_bytes_received
                        }))
                    
                   

                
                elif isinstance(data, str):
                    # 处理文本消息（如控制命令）
                    try:
                        message = json.loads(data)
                        logger.info(f"收到文本消息: {message}")
                        
                        # 命令处理逻辑
                        if message.get("type") == "control":
                            command = message.get("command")
                            
                            if command == "ping":
                                await websocket.send(json.dumps({
                                    "status": "pong",
                                    "timestamp": datetime.now().isoformat()
                                }))
                        
                            

                            elif command == "stop_recording":
                                # 停止录音，触发 Refine
                                logger.info(f"收到停止录音指令: {client_id}")
                                # 向队列发送结束标记
                                if client_id in manager.audio_queues:
                                    manager.audio_queues[client_id].put(b"__STOP__")
                                
                                # Refine 逻辑已移至 asr_consumer 处理 session_end 消息时触发
                                # 这里不再直接处理，避免竞态条件和重复处理

                            elif command == "get_connections":
                                # 获取连接信息
                                connections_info = []
                                for conn_id, conn in manager.active_connections.items():
                                    connections_info.append({
                                        "client_id": conn_id,
                                        "audio_buffer_size": len(manager.audio_buffers.get(conn_id, bytearray()))
                                    })
                                
                                await websocket.send(json.dumps({
                                    "status": "success",
                                    "type": "connections_list",
                                    "data": {
                                        "connections": connections_info,
                                        "total": len(connections_info)
                                    }
                                }))
                            
                            else:
                                # 未知命令
                                await websocket.send(json.dumps({
                                    "status": "error",
                                    "message": f"未知命令: {command}"
                                }))
                    
                        # 其他类型消息处理
                        elif message.get("type") == "config":
                            # 配置更新
                            await websocket.send(json.dumps({
                                "status": "success",
                                "message": "配置已接收",
                                "timestamp": datetime.now().isoformat()
                            }))
                    
                    except json.JSONDecodeError:
                        logger.error(f"无法解析文本消息: {data}")
                        await websocket.send(json.dumps({
                            "status": "error",
                            "message": "无效的JSON格式"
                        }))
                    except Exception as e:
                        logger.error(f"处理文本消息时出错: {str(e)}")
                        await websocket.send(json.dumps({
                            "status": "error",
                            "message": f"处理命令失败: {str(e)}"
                        }))
                
            except websockets.ConnectionClosed:
                logger.info(f"客户端 {client_id} 断开连接")
                
                break
            except Exception as e:
                logger.error(f"处理消息时出错: {str(e)}", exc_info=True)
                
    except Exception as e:
        logger.error(f"建立连接时出错: {str(e)}", exc_info=True)
    finally:
        # 断开连接时保存音频文件
        if 'client_id' in locals():
            # 通知消费者停止并等待结束
            stop_event = manager.get_stop_event(client_id)
            if stop_event:
                stop_event.set()
            try:
                await asyncio.wait_for(consumer_task, timeout=5.0)
            except Exception:
                pass
            

            
            manager.remove_connection(client_id)
            logger.info(f"客户端 {client_id} 会话结束")

# 启动服务器
async def main():
    global asr, text_service
    # 在主进程中初始化 ASR 与文本服务，避免 Windows 多进程递归导入问题
    logger.info("初始化ASRService 与 TextService (本地模式)...")
    asr = ASRService()
    text_service = TextService()


    async with websockets.serve(handle_connection, 'localhost', 12000):
        await asyncio.Future()  # 永久运行


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("服务器已停止")
        sys.exit(0)
    except Exception as e:
        logger.error(f"服务器启动失败: {str(e)}", exc_info=True)
        sys.exit(1)