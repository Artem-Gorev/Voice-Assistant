import io
import wave
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, slots=True)
class SpeechAudio:
    samples: np.ndarray
    sample_rate: int
    processing_time_seconds: float
    model_name: str
    voice: str

    @property
    def duration_seconds(self) -> float:
        return len(self.samples) / self.sample_rate

    @property
    def realtime_factor(self) -> float:
        if self.duration_seconds == 0:
            return 0.0
        return self.processing_time_seconds / self.duration_seconds

    def to_wav_bytes(self) -> bytes:
        pcm = (np.clip(self.samples, -1.0, 1.0) * 32_767).astype("<i2")
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(pcm.tobytes())
        return buffer.getvalue()
