from importlib.resources import files
from json import loads
from logging import DEBUG, basicConfig
from os import environ
from pathlib import Path
from subprocess import run
from sys import executable
from warnings import simplefilter

import google_photos_takeout_model

if INSPECT := False:
    environ["PWDEBUG"] = "1"
albums = Path(f"albums-{'single' if (SINGLE := False) else 'custom'}").with_suffix(
    ".json"
)
basicConfig(
    filename=Path(google_photos_takeout_model.__name__).with_suffix(".log"),
    level=DEBUG,
)
for warning in [ResourceWarning, RuntimeWarning]:
    simplefilter("error", warning)
environ["PYTHONASYNCIODEBUG"] = "1"
run(
    [
        executable,
        *(["-X", "frozen_modules=off"] if environ.get("DEBUGPY_RUNNING") else []),
        Path(files(google_photos_takeout_model)) / "get_media_metadata.py",  # pyright: ignore[reportArgumentType]
        *loads(albums.read_text(encoding="utf-8")),
    ]
)
