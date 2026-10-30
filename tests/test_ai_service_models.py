import unittest

from backend.ai_service.stt.config import TOneConfig
from backend.ai_service.stt.result import Transcription, TranscriptionSegment
from backend.ai_service.tts.config import SileroConfig
from backend.ai_service.tts.result import SpeechAudio
from backend.ai_service.ttv.config import RuBertTiny2Config
from backend.ai_service.ttv.result import SearchResult, TextVectors


class TestAiServiceModels(unittest.TestCase):
    def test_stt_tone_config_defaults(self):
        config = TOneConfig()
        self.assertEqual(config.model_id, "t-tech/T-one")
        self.assertEqual(config.decoder, "greedy")

    def test_stt_transcription_properties(self):
        seg1 = TranscriptionSegment(text="Привет", start_seconds=0.0, end_seconds=0.5)
        seg2 = TranscriptionSegment(text="мир", start_seconds=0.6, end_seconds=1.0)
        t = Transcription(
            text="Привет мир",
            segments=(seg1, seg2),
            audio_duration_seconds=2.0,
            processing_time_seconds=0.5,
            model_name="t_one",
            sample_rate=16000,
        )
        self.assertEqual(t.text, "Привет мир")
        self.assertEqual(len(t.segments), 2)
        self.assertAlmostEqual(t.realtime_factor, 0.25)

    def test_stt_transcription_zero_duration(self):
        t = Transcription(
            text="",
            segments=(),
            audio_duration_seconds=0.0,
            processing_time_seconds=0.1,
            model_name="t_one",
            sample_rate=16000,
        )
        self.assertEqual(t.realtime_factor, 0.0)

    def test_tts_silero_config_defaults(self):
        config = SileroConfig()
        self.assertEqual(config.voice, "xenia")
        self.assertEqual(config.sample_rate, 24000)
        self.assertEqual(config.device, "cpu")

    def test_tts_speech_audio_duration_and_rtf(self):
        class DummySamples:
            def __len__(self):
                return 48000

        audio = SpeechAudio(
            samples=DummySamples(),
            sample_rate=24000,
            processing_time_seconds=0.4,
            model_name="silero",
            voice="xenia",
        )
        self.assertAlmostEqual(audio.duration_seconds, 2.0)
        self.assertAlmostEqual(audio.realtime_factor, 0.2)

    def test_ttv_rubert_config_defaults(self):
        config = RuBertTiny2Config()
        self.assertEqual(config.model_id, "cointegrated/rubert-tiny2")
        self.assertEqual(config.batch_size, 32)
        self.assertEqual(config.device, "auto")

    def test_ttv_search_result(self):
        res1 = SearchResult(index=0, text="А", score=0.85)
        res2 = SearchResult(index=1, text="Б", score=0.92)
        results = [res1, res2]
        results.sort(key=lambda item: item.score, reverse=True)
        self.assertEqual(results[0].text, "Б")
        self.assertEqual(results[0].score, 0.92)

    def test_ttv_text_vectors_dimension_and_single_vector(self):
        class MockMatrix:
            shape = (1, 312)

            def __getitem__(self, idx):
                return [0.1] * 312

        vectors = TextVectors(
            vectors=MockMatrix(),
            texts=("Тестовый текст",),
            processing_time_seconds=0.05,
            model_name="rubert_tiny2",
        )
        self.assertEqual(vectors.dimension, 312)
        self.assertEqual(len(vectors.vector), 312)


if __name__ == "__main__":
    unittest.main()
