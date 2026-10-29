from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TranscriptionSegment:
    text: str
    start_seconds: float
    end_seconds: float


@dataclass(frozen=True, slots=True)
class Transcription:
    text: str
    segments: tuple[TranscriptionSegment, ...]
    audio_duration_seconds: float
    processing_time_seconds: float
    model_name: str
    sample_rate: int

    @property
    def realtime_factor(self) -> float:
        if self.audio_duration_seconds == 0:
            return 0.0
        return self.processing_time_seconds / self.audio_duration_seconds
