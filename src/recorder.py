"""Audio recording via sounddevice → in-memory WAV buffer."""
import io
import threading
import wave

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16_000
CHANNELS = 1
DTYPE = "int16"


class Recorder:
    def __init__(self):
        self._frames: list[np.ndarray] = []
        self._stream: sd.InputStream | None = None
        self._lock = threading.Lock()
        self.is_recording = False

    def start(self):
        """Start capturing audio from the default microphone."""
        with self._lock:
            if self.is_recording:
                return
            self._frames = []
            self.is_recording = True

        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=DTYPE,
            callback=self._callback,
        )
        self._stream.start()

    def _callback(self, indata: np.ndarray, frames: int, time, status):
        if self.is_recording:
            with self._lock:
                self._frames.append(indata.copy())

    def stop(self) -> io.BytesIO | None:
        """Stop recording and return a WAV BytesIO ready for the Whisper API.
        Returns None if no audio was captured."""
        with self._lock:
            self.is_recording = False

        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        with self._lock:
            frames = list(self._frames)

        if not frames:
            return None

        audio = np.concatenate(frames, axis=0)
        return _to_wav(audio)


def _to_wav(audio: np.ndarray) -> io.BytesIO:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)  # int16 → 2 bytes per sample
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio.tobytes())
    buf.seek(0)
    buf.name = "audio.wav"  # Whisper API needs a filename attribute
    return buf
