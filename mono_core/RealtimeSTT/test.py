
from email.mime import audio
from audio_recorder import AudioToTextRecorder
import multiprocessing
import os
import logging
import pyaudio
import numpy as np 
import threading
recorder: AudioToTextRecorder | None = None
#C:\Users\Hu\.cache\modelscope\hub\models\iic\SenseVoiceSmall-onnx
def main():
    # recorder = AudioToTextRecorder(
    #     model_path="./models/sensevoice_small",
    #     silero_use_onnx=True,
    #     silero_deactivity_detection=True,
    # )

    recorder = AudioToTextRecorder(
        model_path="iic/SenseVoiceSmall-onnx",
        silero_use_onnx=True,
        silero_deactivity_detection=True,
    )

    while True:
       text = recorder.text()
       print(f"ASR: {text}")


def test_manual_transcribe():
    # 手动转写测试
    # 用户用户按下s键开始录音，按下q键结束录音并转写

    model_path = "iic/SenseVoiceSmall-onnx"
    recorder = AudioToTextRecorder(
        model_path="iic/SenseVoiceSmall-onnx",
        silero_use_onnx=True,
        silero_deactivity_detection=True,
        
    )

    print("Press 's' to start recording, 'q' to stop and transcribe, 'e' to exit.")

    while True:
        key = input("Press 's' to start recording, 'q' to stop and transcribe, 'e' to exit.\n")
        if key == "s":
            print("Recording... Press 'q' to stop.")
            recorder.start()
        elif key == "q":
            print("Stopping recording...")
            recorder.stop()
            text = recorder.text()
            print(f"Transcription: {text}")
        elif key == "e":
            print("Exiting...")
            break


def test_manual_start_microphone():
    # 手动转写测试
    # 用户用户按下s键开始录音，按下q键结束录音并转写
    recorder = AudioToTextRecorder(
        model_path="iic/SenseVoiceSmall-onnx",
        silero_use_onnx=True,
        silero_deactivity_detection=True,
        use_microphone=False
    )


    p = pyaudio.PyAudio()
    stream = None
    audio_data = np.array([], dtype=np.int16)
    recording = False
    record_thread = None

    def record_audio():
        nonlocal audio_data, stream, recording
        while recording and stream is not None:
            data = stream.read(1024)
            # 将数据转换为numpy数组
            data = np.frombuffer(data, dtype=np.int16)
            audio_data = np.concatenate((audio_data, data))

    while True:
        key = input("Press 's' to start recording, 'q' to stop and transcribe, 'e' to exit.\n")
        if key == "s":
            if recording:
                print("Already recording, press 'q' to stop.")
                continue

            print("Recording... Press 'q' to stop.")
            audio_data = np.array([], dtype=np.int16)
            stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                frames_per_buffer=1024,
                input_device_index=0,
            )
            recording = True
            record_thread = threading.Thread(target=record_audio, daemon=True)
            record_thread.start()

        elif key == "q":
            if not recording:
                print("Not recording, press 's' to start.")
                continue

            print("Stopping recording...")
            recording = False
            if record_thread is not None:
                record_thread.join()
                record_thread = None
            if stream is not None:
                stream.stop_stream()
                stream.close()
                stream = None

            print(f'audio_data length: {len(audio_data)}')
            if len(audio_data) == 0:
                print("No audio captured.")
                continue

            recorder.audio = audio_data.astype(np.float32) / 32768.0
            text = recorder.transcribe()
            print(f"Transcription: {text}")
        elif key == "e":
            print("Exiting...")
            if recording:
                recording = False
                if record_thread is not None:
                    record_thread.join()
                if stream is not None:
                    stream.stop_stream()
                    stream.close()
            p.terminate()
            break

def local_file_transcribe( ):
    recorder = AudioToTextRecorder(
        model_path="iic/SenseVoiceSmall-onnx",
        silero_use_onnx=True,
        silero_deactivity_detection=True,
        use_microphone=False
    )
    audio_path = r"C:\Users\Hu\Downloads\未命名.wav"
    import soundfile as sf
    audio_data, samplerate = sf.read(audio_path, dtype='int16')
    recorder.audio = audio_data
    text = recorder.transcribe()
    
    print(f"Transcription: {text}")

if __name__ == '__main__':
    multiprocessing.freeze_support()  # # 为了 Windows 打包兼容
    # main()
    # test_manual_transcribe()
    test_manual_start_microphone()
    # local_file_transcribe()
