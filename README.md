# PRIMETONE STEMS — v0.3

Local AI stem separation (Demucs) with a mixer (solo/mute/volume/export) and an offline model manager.

## Run from source (Windows: just double-click START.bat)
See START.bat, or: create a Python 3.11 venv, `pip install -r requirements.txt`, `python run.py`.
Models live in `./models`. Open the **MODELS** tab and press **Download** once (internet), after that it works offline.
Already downloaded models with v0.2? Use **Import model files (.th)…**, pick the files from
`C:\Users\<you>\.cache\torch\hub\checkpoints`, then press **Verify / Update** (no download if files exist).

## Build the offline Windows installer (no local coding)
1. Create a free account at github.com, then a **new private repository**.
2. Upload the contents of this folder (**Add file → Upload files**; drag everything in).
   The hidden `.github` folder must be included. If it isn't, use **Add file → Create new file**, name it
   `.github/workflows/build-windows.yml`, and paste the file's contents.
3. Open the **Actions** tab → **Build Windows installer** → **Run workflow**.
4. Wait about 30-60 minutes. Open the finished run, download the **PRIMETONE_STEMS_Setup** artifact, unzip it.
5. `PRIMETONE_STEMS_Setup.exe` installs per-user, with the three models inside; no internet needed to run.

Notes: the build uses CPU-only PyTorch (no NVIDIA GPU acceleration, much smaller). Expect a large installer
(over 1 GB). Unsigned installers trigger a Windows SmartScreen warning; selling it needs a code-signing certificate.

## Licensing
Check the license of every model/dependency (Demucs and its weights, PySide6/LGPL, torch, ffmpeg) before selling.
