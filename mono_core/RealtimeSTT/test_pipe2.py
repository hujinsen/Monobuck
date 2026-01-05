import multiprocessing as mp
import time

def child_process(conn, ready_event):
    """子进程：接收消息，回复结果"""
    print("[子进程] 启动完成，等待接收消息...")
    
    # 通知父进程子进程已准备好
    ready_event.set()
    
    message = conn.recv()  # 从父进程接收
    print(f"[子进程] 收到: {message}")
    
    # 回复结果
    conn.send(f"已处理: {message.upper()}")
    print("[子进程] 已回复")

if __name__ == "__main__":
    # 创建双向管道
    parent_conn, child_conn = mp.Pipe(duplex=True)
    
    # 创建同步事件
    ready_event = mp.Event()

    # 启动子进程
    p = mp.Process(target=child_process, args=(child_conn, ready_event))
    p.start()
    
    # 等待子进程准备好
    ready_event.wait()
    print("[父进程] 子进程已准备好")
    
    # 父进程发送消息
    parent_conn.send("Hello from parent!")
    print("[父进程] 已发送消息")

    # 等待子进程回复
    reply = parent_conn.recv()
    print(f"[父进程] 收到回复: {reply}")

    p.join()  # 等待子进程结束
