"""Browser-side audio capture and assistant speech playback scripts."""

import json
import os


def _api_url() -> str:
    return os.getenv("ASSISTANT_API_URL", "http://127.0.0.1:8000/api/v1").rstrip("/")


def start_recording_script() -> str:
    endpoint = json.dumps(f"{_api_url()}/voice/transcribe")
    return f"""(async () => {{
      try {{
        if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {{
          return "ERROR: Этот браузер не поддерживает запись аудио.";
        }}
        const stream = await navigator.mediaDevices.getUserMedia({{audio: true}});
        const mime = ["audio/webm;codecs=opus", "audio/mp4", "audio/webm"]
          .find(type => MediaRecorder.isTypeSupported(type));
        const recorder = new MediaRecorder(stream, mime ? {{mimeType: mime}} : undefined);
        const chunks = [];
        let recordingError = "";
        window.__assistantRecorder = recorder;
        window.__assistantRecordingDone = new Promise(resolve => {{
          window.__assistantResolveRecording = resolve;
        }});
        recorder.ondataavailable = event => {{ if (event.data.size) chunks.push(event.data); }};
        recorder.onerror = event => {{
          recordingError = event.error?.message || "Ошибка записи микрофона.";
          if (recorder.state !== "inactive") recorder.stop();
        }};
        recorder.onstop = async () => {{
          let context;
          try {{
            if (recordingError) throw new Error(recordingError);
            const blob = new Blob(chunks, {{type: recorder.mimeType || "audio/webm"}});
            const AudioContextClass = window.AudioContext || window.webkitAudioContext;
            context = new AudioContextClass();
            const decoded = await context.decodeAudioData(await blob.arrayBuffer());
            const targetRate = 8000;
            const length = Math.ceil(decoded.duration * targetRate);
            if (!length || length > targetRate * 60) throw new Error("Запись должна быть короче 60 секунд.");
            const channels = Array.from({{length: decoded.numberOfChannels}}, (_, i) => decoded.getChannelData(i));
            const pcm = new Int16Array(length);
            for (let i = 0; i < length; i++) {{
              const position = i * decoded.sampleRate / targetRate;
              const left = Math.floor(position);
              const fraction = position - left;
              let sample = 0;
              for (const channel of channels) {{
                const a = channel[Math.min(left, channel.length - 1)] || 0;
                const b = channel[Math.min(left + 1, channel.length - 1)] || 0;
                sample += a + (b - a) * fraction;
              }}
              sample /= channels.length;
              pcm[i] = Math.max(-1, Math.min(1, sample)) * (sample < 0 ? 32768 : 32767);
            }}
            const wav = new ArrayBuffer(44 + pcm.length * 2);
            const view = new DataView(wav);
            const write = (offset, value) => {{ for (let i = 0; i < value.length; i++) view.setUint8(offset + i, value.charCodeAt(i)); }};
            write(0, "RIFF"); view.setUint32(4, wav.byteLength - 8, true); write(8, "WAVE");
            write(12, "fmt "); view.setUint32(16, 16, true); view.setUint16(20, 1, true);
            view.setUint16(22, 1, true); view.setUint32(24, targetRate, true);
            view.setUint32(28, targetRate * 2, true); view.setUint16(32, 2, true);
            view.setUint16(34, 16, true); write(36, "data"); view.setUint32(40, pcm.length * 2, true);
            for (let i = 0; i < pcm.length; i++) view.setInt16(44 + i * 2, pcm[i], true);
            const response = await fetch({endpoint}, {{method: "POST", headers: {{"Content-Type": "audio/wav"}}, body: wav}});
            const data = await response.json();
            if (!response.ok) throw new Error(data.detail || "Не удалось распознать речь.");
            window.__assistantResolveRecording(data.text || "");
          }} catch (error) {{
            window.__assistantResolveRecording("ERROR: " + (error.message || "Не удалось обработать запись."));
          }} finally {{
            if (context && context.state !== "closed") await context.close();
            stream.getTracks().forEach(track => track.stop());
            window.__assistantRecorder = null;
          }}
        }};
        recorder.start();
        return "recording";
      }} catch (error) {{
        return "ERROR: " + (error.message || "Нет доступа к микрофону.");
      }}
    }})()"""


def stop_recording_script() -> str:
    return """(async () => {
      const recorder = window.__assistantRecorder;
      if (!recorder) return "ERROR: Запись не запущена.";
      const completed = window.__assistantRecordingDone;
      recorder.stop();
      return await completed;
    })()"""


def speak_text_script(text: str) -> str:
    endpoint = json.dumps(f"{_api_url()}/speech")
    safe_text = json.dumps(text, ensure_ascii=False)
    return f"""(async () => {{
      try {{
        const response = await fetch({endpoint}, {{
          method: "POST", headers: {{"Content-Type": "application/json"}},
          body: JSON.stringify({{text: {safe_text}}})
        }});
        if (!response.ok) throw new Error("TTS unavailable");
        const url = URL.createObjectURL(await response.blob());
        const audio = new Audio(url);
        window.__assistantSpeechAudio = audio;
        audio.onended = () => {{ URL.revokeObjectURL(url); window.__assistantSpeechAudio = null; }};
        await audio.play();
      }} catch (_) {{
        if (window.speechSynthesis) {{
          window.speechSynthesis.cancel();
          const utterance = new SpeechSynthesisUtterance({safe_text});
          utterance.lang = "ru-RU";
          window.speechSynthesis.speak(utterance);
        }}
      }}
    }})()"""
