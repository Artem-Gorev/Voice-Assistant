import io
import wave
import numpy as np
import sounddevice as sd


class AudioHandler:
    def __init__(self, logger):
        self.logger = logger
        self.recording = False
        self.audio_buffer = io.BytesIO()

    def start_recording(self):
        self.logger.info("Начало записи аудио")
        self.recording = True
        self.audio_buffer = io.BytesIO()

    def add_chunk(self, chunk: bytes):
        if self.recording:
            self.audio_buffer.write(chunk)

    def stop_recording(self) -> bytes:
        self.logger.info("Запись аудио остановлена")
        self.recording = False
        self.audio_buffer.seek(0)
        return self.audio_buffer.read()

    def play_audio(self, audio_wav_bytes: bytes):
        self.logger.info("Воспроизведение аудио...")
        try:
            with wave.open(io.BytesIO(audio_wav_bytes), "rb") as wf:
                data = np.frombuffer(
                    wf.readframes(wf.getnframes()),
                    dtype=np.int16
                ).astype(np.float32) / 32767.0

                sample_rate = wf.getframerate()

                sd.play(data, samplerate=sample_rate)
                sd.wait()

            self.logger.info("Воспроизведение завершено")
        except Exception as e:
            self.logger.error(f"Ошибка при воспроизведении аудио: {e}")