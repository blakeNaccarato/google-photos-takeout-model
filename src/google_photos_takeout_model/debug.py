from importlib.resources import files
from json import loads
from os import environ
from pathlib import Path
from subprocess import run
from sys import executable

import google_photos_takeout_model

run(
    [
        executable,
        *(["-X", "frozen_modules=off"] if environ.get("DEBUGPY_RUNNING") else []),
        Path(files(google_photos_takeout_model)) / "get_media_metadata.py",  # pyright: ignore[reportArgumentType]
        *loads(Path("albums-custom.json").read_text(encoding="utf-8")),
    ]
)
