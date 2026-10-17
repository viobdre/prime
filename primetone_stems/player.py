"""Real-time stem mixer: per-stem gain, mute, solo, seek, and mix export."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf

STEM_ORDER = ["vocals", "drums", "bass", "other"]


class StemPlayer:
    def __init__(self) -> None:
        self.names: list[str] = []
        self.data: dict[str, np.ndarray] = {}  # int16, shape (frames, 2)
        self.rate = 44100
        self.frames = 0
        self.gain: dict[str, float] = {}
        self.muted: frozenset[str] = frozenset()
        self.soloed: frozenset[str] = frozenset()
        self.pos = 0
        self.ended = False
        self._stream: sd.OutputStream | None = None

    # ---- state -------------------------------------------------------
    @property
    def loaded(self) -> bool:
        return bool(self.names)

    @property
    def position(self) -> float:
        return self.pos / self.rate

    @property
    def duration(self) -> float:
        return self.frames / self.rate

    @property
    def is_playing(self) -> bool:
        return self._stream is not None and self._stream.active

    def set_gain(self, name: str, value: float) -> None:
        self.gain[name] = value

    def set_mute(self, name: str, on: bool) -> None:
        self.muted = self.muted | {name} if on else self.muted - {name}

    def set_solo(self, name: str, on: bool) -> None:
        self.soloed = self.soloed | {name} if on else self.soloed - {name}

    def effective_gains(self) -> dict[str, float]:
        audible = self.soloed if self.soloed else frozenset(self.names) - self.muted
        return {n: (self.gain.get(n, 1.0) if n in audible else 0.0) for n in self.names}

    # ---- loading -----------------------------------------------------
    def load(self, folder: Path) -> None:
        self.close()
        wavs = {p.stem: p for p in Path(folder).glob("*.wav")}
        if not wavs:
            raise ValueError(f"No .wav stems found in {folder}")
        order = [n for n in STEM_ORDER if n in wavs] + sorted(n for n in wavs if n not in STEM_ORDER)
        data: dict[str, np.ndarray] = {}
        rate = None
        for name in order:
            arr, sr = sf.read(str(wavs[name]), dtype="int16", always_2d=True)
            if rate is None:
                rate = sr
            elif sr != rate:
                raise ValueError("Stems have different sample rates.")
            if arr.shape[1] == 1:
                arr = np.repeat(arr, 2, axis=1)
            data[name] = np.ascontiguousarray(arr[:, :2])
        frames = max(a.shape[0] for a in data.values())
        for name, arr in data.items():
            if arr.shape[0] < frames:
                data[name] = np.pad(arr, ((0, frames - arr.shape[0]), (0, 0)))
        self.names, self.data, self.rate, self.frames = order, data, int(rate), frames
        self.gain = {n: 1.0 for n in order}
        self.muted = frozenset()
        self.soloed = frozenset()
        self.pos, self.ended = 0, False

    # ---- mixing ------------------------------------------------------
    def _mix(self, start: int, n: int, gains: dict[str, float]) -> np.ndarray:
        out = np.zeros((n, 2), dtype=np.float32)
        end = min(start + n, self.frames)
        if end > start:
            for name, g in gains.items():
                if g > 0:
                    out[: end - start] += self.data[name][start:end].astype(np.float32) * (g / 32768.0)
            np.clip(out, -1.0, 1.0, out=out)
        return out

    def _callback(self, outdata, frames, time, status) -> None:  # audio thread
        outdata[:] = self._mix(self.pos, frames, self.effective_gains())
        self.pos = min(self.pos + frames, self.frames)
        if self.pos >= self.frames:
            self.ended = True
            raise sd.CallbackStop

    # ---- transport ---------------------------------------------------
    def _close_stream(self) -> None:
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:  # noqa: BLE001
                pass
            self._stream = None

    def play(self) -> None:
        if not self.loaded:
            return
        if self.pos >= self.frames:
            self.pos = 0
        self.ended = False
        self._close_stream()
        self._stream = sd.OutputStream(
            samplerate=self.rate, channels=2, dtype="float32", callback=self._callback
        )
        self._stream.start()

    def pause(self) -> None:
        self._close_stream()

    def stop(self) -> None:
        self._close_stream()
        self.pos, self.ended = 0, False

    def seek(self, seconds: float) -> None:
        self.pos = max(0, min(self.frames, int(seconds * self.rate)))
        self.ended = False

    def close(self) -> None:
        self._close_stream()
        self.names, self.data, self.frames, self.pos = [], {}, 0, 0

    # ---- export ------------------------------------------------------
    def export_mix(self, path: str) -> None:
        gains = self.effective_gains()
        step = 1 << 16
        with sf.SoundFile(path, "w", samplerate=self.rate, channels=2, subtype="PCM_16") as f:
            for start in range(0, self.frames, step):
                f.write(self._mix(start, min(step, self.frames - start), gains))
