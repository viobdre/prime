"""Background subprocess workers: separation and model fetch (cancellable)."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from primetone_stems import paths

PERCENT = re.compile(r"(\d{1,3})%")


def launcher_command(*args: str) -> list[str]:
    """Re-run this app (frozen) or run.py (source) in a worker mode."""
    if getattr(sys, "frozen", False):
        return [sys.executable, *args]
    return [sys.executable, str(paths.app_dir() / "run.py"), *args]


class _ProcessWorker(QThread):
    log_line = Signal(str)
    progress = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        self._proc: subprocess.Popen | None = None
        self._cancel = False
        self.tail: list[str] = []

    def cancel(self) -> None:
        self._cancel = True
        proc = self._proc
        if proc is not None and proc.poll() is None:
            proc.terminate()

    def _handle_line(self, line: str) -> None:
        if not line:
            return
        match = PERCENT.search(line)
        if match:
            self.progress.emit(min(99, int(match.group(1))))
        if "%|" in line:  # tqdm bar: progress only, keep out of the log
            return
        self.tail = (self.tail + [line])[-6:]
        self.log_line.emit(line)

    def _stream(self, command: list[str]) -> int:
        self.log_line.emit("$ " + " ".join(f'"{p}"' if " " in p else p for p in command))
        env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8")
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        self._proc = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, creationflags=flags
        )
        assert self._proc.stdout is not None
        buf = b""
        while True:
            chunk = self._proc.stdout.read1(4096)
            if not chunk:
                break
            buf += chunk
            parts = re.split(rb"[\r\n]", buf)
            buf = parts.pop()
            for raw in parts:
                self._handle_line(raw.decode("utf-8", "replace").strip())
        if buf:
            self._handle_line(buf.decode("utf-8", "replace").strip())
        return self._proc.wait()


class SeparationWorker(_ProcessWorker):
    succeeded = Signal(str)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, audio_path: Path, output_dir: Path, model: str, extra: list[str]) -> None:
        super().__init__()
        self.audio_path, self.output_dir, self.model, self.extra = audio_path, output_dir, model, extra

    def run(self) -> None:
        if shutil.which("ffmpeg") is None:
            self.log_line.emit("Note: ffmpeg not found. MP3/M4A/OGG may fail to load; WAV/FLAC are safest.")
        args = ["--demucs", "-n", self.model, *self.extra, "--out", str(self.output_dir), str(self.audio_path)]
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            code = self._stream(launcher_command(*args))
            if self._cancel:
                self.cancelled.emit()
                return
            if code != 0:
                self.failed.emit(
                    "Separation failed. See the log. If the model isn't installed and you're offline, "
                    "install it from the Models tab."
                )
                return
            result = self.output_dir / self.model / self.audio_path.stem
            if not result.exists() or not list(result.glob("*.wav")):
                self.failed.emit(f"Demucs finished but no stems were found in:\n{result}")
                return
            self.progress.emit(100)
            self.succeeded.emit(str(result))
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


class FetchWorker(_ProcessWorker):
    done = Signal(str)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, model: str) -> None:
        super().__init__()
        self.model = model

    def run(self) -> None:
        try:
            code = self._stream(launcher_command("--fetch-model", self.model))
            if self._cancel:
                self.cancelled.emit()
            elif code != 0:
                last = "\n".join(self.tail[-3:])
                self.failed.emit(
                    f"Could not prepare '{self.model}'. If the files aren't on this computer yet, "
                    f"check your internet connection and try again.\n\n{last}"
                )
            else:
                self.progress.emit(100)
                self.done.emit(self.model)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
