import logging
import threading
import time
import os
import signal as system_signal
import queue
from typing import Any, Tuple

import soundfile as sf
from funasr_onnx import SenseVoiceSmall
from funasr_onnx.utils.postprocess_utils import rich_transcription_postprocess

try:  # 在作为 RealtimeSTT 包使用时优先采用包内相对导入
    from .utils import check_parent_process
except ImportError:  # 当在 RealtimeSTT/ 目录下以脚本运行时，退回使用本地导入
    from utils import check_parent_process


class TranscriptionWorker:
    """持有 SenseVoice 模型并执行语音识别（ASR）的独立子进程。

    与主进程通过多进程 Pipe 通信：
    - 父进程发送 (audio_np_array, language)
    - 子进程返回 ("success", text) 或 ("error", message)
    """

    def __init__(self, conn, stdout_pipe, model_path, ready_event, shutdown_event, interrupt_stop_event):
        self.conn = conn
        self.stdout_pipe = stdout_pipe
        self.model_path = model_path
        self.ready_event = ready_event
        self.shutdown_event = shutdown_event
        self.interrupt_stop_event = interrupt_stop_event
        self.queue: "queue.Queue[Tuple[Any, str]]" = queue.Queue()

    def custom_print(self, *args, **kwargs) -> None:
        message = " ".join(map(str, args))
        try:
            self.stdout_pipe.send(message)
        except (BrokenPipeError, EOFError, OSError):
            # 父进程已关闭管道；之后的打印直接忽略
            pass

    def poll_connection(self) -> None:
        """
    Continuously polls a connection for incoming data and puts it into a queue.
    
    This method runs in a loop until shutdown_event is set, checking for new data from the connection.
    Received data is placed into an internal queue for processing. The method handles connection
    errors gracefully with logging.
    
    Raises:
        Exception: Logs any errors encountered during polling or data receiving,
                  including connection errors and queue operations.
    """
        while not self.shutdown_event.is_set():
            check_parent_process(self.shutdown_event)

            try:
                if self.conn.poll(0.01):
                    try:
                        data = self.conn.recv()
                        self.queue.put(data)
                    except Exception as e:  # noqa: BLE001
                        logging.error("Error receiving data from connection: %s", e, exc_info=True)
                else:
                    time.sleep(0.02)
            except (BrokenPipeError, EOFError, OSError) as e:  # 管道被父进程关闭或句柄失效
                # 这种情况通常发生在主进程正常退出或显式关闭转写器时，
                # 不需要打印成严重错误，直接结束轮询线程即可。
                logging.info("Connection closed in poll_connection: %s", e)
                break
            except Exception as e:  # noqa: BLE001
                logging.error("Error in poll_connection: %s", e, exc_info=True)
                break

        try:
            self.conn.close()
        except Exception:
            pass

    def run(self) -> None:
        # 子进程应忽略 SIGINT，由父进程统一处理 Ctrl+C
        if __name__ == "__main__":
            system_signal.signal(system_signal.SIGINT, system_signal.SIG_IGN)
            __builtins__["print"] = self.custom_print

        logging.info("Initializing sense voice main transcription model %s", self.model_path)

        try:
            model = SenseVoiceSmall(self.model_path, batch_size=1, quantize=True, )

            # 进行一次预热推理，以摊平第一次调用的延迟
            current_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "assets")
            warmup_audio_path = os.path.join(current_dir, "warmup_audio.wav")

            warmup_audio_data, _ = sf.read(warmup_audio_path, dtype="float32")
            model(wav_content=warmup_audio_data, language="auto", textnorm="withitn")
        except Exception as e:  # noqa: BLE001
            logging.exception("Error initializing main sense voice transcription model: %s", e)
            raise

        self.ready_event.set()
        logging.debug("SenseVoice main speech to text transcription model initialized successfully")

        # 启动后台轮询线程
        polling_thread = threading.Thread(target=self.poll_connection)
        polling_thread.start()

        try:
            while not self.shutdown_event.is_set():
                check_parent_process(self.shutdown_event)

                try:
                    audio, language = self.queue.get(timeout=0.1)
                    try:
                        logging.debug("Transcribing audio with language %s", language)
                        result = model(
                            audio,
                            language=language if language else "auto",
                            textnorm="withitn",
                        )
                        transcription = " ".join(
                            rich_transcription_postprocess(seg) for seg in result
                        ).strip()
                        logging.debug("Final text detected with main model: %s", transcription)
                        # 发送转写结果
                        self.conn.send(("success", transcription))

                    except Exception as e:  # noqa: BLE001
                        logging.error("General error in transcription: %s", e, exc_info=True)
                        self.conn.send(("error", str(e)))
                except queue.Empty:
                    continue
                except KeyboardInterrupt:
                    self.interrupt_stop_event.set()
                    logging.debug("Transcription worker process finished due to KeyboardInterrupt")
                    break
                except Exception as e:  # noqa: BLE001
                    logging.error("General error in processing queue item: %s", e, exc_info=True)
        finally:
            __builtins__["print"] = print  # type: ignore[assignment]
            self.conn.close()
            self.stdout_pipe.close()
            self.shutdown_event.set()
            polling_thread.join()


def run_transcription_worker(*args, **kwargs) -> None:
    """作为多进程目标函数的入口方法。"""
    worker = TranscriptionWorker(*args, **kwargs)
    worker.run()
