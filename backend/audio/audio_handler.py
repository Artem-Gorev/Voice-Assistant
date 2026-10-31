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


def decode_audio_bytes(audio_bytes: bytes, sample_rate: int = 8_000) -> np.ndarray:
    """Decode browser-recorded audio (WebM/Opus or MP4/AAC) to mono float audio."""
    if not audio_bytes:
        raise ValueError("Получена пустая аудиозапись")

    try:
        import av
    except ImportError as error:
        raise RuntimeError("Для обработки аудио установите PyAV: pip install av") from error

    try:
        with av.open(io.BytesIO(audio_bytes)) as container:
            audio_stream = next(
                (stream for stream in container.streams if stream.type == "audio"),
                None,
            )
            if audio_stream is None:
                raise ValueError("В записи не найдена аудиодорожка")

            resampler = av.AudioResampler(format="fltp", layout="mono", rate=sample_rate)
            chunks: list[np.ndarray] = []
            for frame in container.decode(audio=audio_stream.index):
                for converted in resampler.resample(frame):
                    chunks.append(converted.to_ndarray().reshape(-1))
            for converted in resampler.resample(None):
                chunks.append(converted.to_ndarray().reshape(-1))

    except ValueError:
        raise
    except Exception as error:
        raise ValueError(f"Не удалось декодировать аудиозапись: {error}") from error

    if not chunks:
        raise ValueError("В аудиозаписи нет звуковых данных")
    return np.concatenate(chunks).astype(np.float32, copy=False)
