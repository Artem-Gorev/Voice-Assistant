import io
import wave

import numpy as np


class AudioHandler:
    def __init__(self, logger):
        self.logger = logger
        self.recording = False
        self.audio_buffer = io.BytesIO()
        self._sounddevice = None

    def _get_sounddevice(self):
        if self._sounddevice is None:
            import sounddevice

            self._sounddevice = sounddevice
        return self._sounddevice

    def record_audio(self, duration_seconds: float, sample_rate: int) -> np.ndarray:
        if duration_seconds <= 0:
            raise ValueError("Продолжительность записи должна быть больше нуля")
        if sample_rate <= 0:
            raise ValueError("Частота дискретизации должна быть больше нуля")

        self.logger.info(f"[AUDIO]: Запись аудио: {duration_seconds:.1f} сек., {sample_rate} Гц")
        sounddevice = self._get_sounddevice()
        audio = sounddevice.rec(
            int(duration_seconds * sample_rate),
            samplerate=sample_rate,
            channels=1,
            dtype="float32",
        )
        sounddevice.wait()
        return audio

    def start_recording(self):
        self.logger.info("[AUDIO]: Начало записи аудио")
        self.recording = True
        self.audio_buffer = io.BytesIO()

    def add_chunk(self, chunk: bytes):
        if self.recording:
            self.audio_buffer.write(chunk)

    def stop_recording(self) -> bytes:
        self.logger.info("[AUDIO]: Запись аудио остановлена")
        self.recording = False
        self.audio_buffer.seek(0)
        return self.audio_buffer.read()

    def play_audio(self, audio_wav_bytes: bytes):
        self.logger.info("[AUDIO]: Воспроизведение аудио...")
        try:
            with wave.open(io.BytesIO(audio_wav_bytes), "rb") as wf:
                data = np.frombuffer(
                    wf.readframes(wf.getnframes()),
                    dtype=np.int16
                ).astype(np.float32) / 32767.0

                sample_rate = wf.getframerate()

                sounddevice = self._get_sounddevice()
                sounddevice.play(data, samplerate=sample_rate)
                sounddevice.wait()

            self.logger.info("[AUDIO]: Воспроизведение завершено")
        except Exception as e:
            self.logger.exception(f"[AUDIO]: Ошибка при воспроизведении аудио: {e}")
