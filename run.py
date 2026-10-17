"""Launcher / PyInstaller entry point.

Modes (used internally so a frozen build never needs a separate Python):
  run.py                       -> start the GUI
  run.py --demucs <args>       -> run Demucs separation
  run.py --fetch-model <name>  -> download/verify a model (offline if already present)
"""
import multiprocessing
import sys

if __name__ == "__main__":
    multiprocessing.freeze_support()
    from primetone_stems.paths import configure_env

    configure_env()
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "--demucs":
        from demucs.separate import main as demucs_main

        demucs_main(sys.argv[2:])
    elif mode == "--fetch-model":
        from demucs.pretrained import get_model
        from primetone_stems.paths import mark_installed

        name = sys.argv[2]
        print(f"Preparing model {name} (downloads only if files are missing)...", flush=True)
        get_model(name)
        mark_installed(name)
        print("Model ready.", flush=True)
    else:
        from primetone_stems.app import main

        main()
