import io

class AudioRecorder:
    def __init__(self):
        self.recording = False
        self.audio_buffer = io.BytesIO()

    def start_recording(self):
        self.recording = True
        self.audio_buffer = io.BytesIO()

    def add_chunk(self, chunk: bytes):
        if self.recording:
            self.audio_buffer.write(chunk)

    def stop_recording(self) -> bytes:
        self.recording = False
        self.audio_buffer.seek(0)
        return self.audio_buffer.read()