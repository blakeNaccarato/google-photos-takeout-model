import logging
from importlib.resources import files
from json import loads
from logging import basicConfig
from os import environ
from pathlib import Path
from subprocess import run
from sys import executable
from warnings import simplefilter

import google_photos_takeout_model

DEBUG, SINGLE, ALT, INSPECT, CLEAR = False, False, True, False, False
if INSPECT:
    environ["PWDEBUG"] = "1"
albums = Path(f"albums-{'single' if SINGLE else 'custom'}.json")
if DEBUG:
    environ["PYTHONASYNCIODEBUG"] = "1"
    basicConfig(
        filename=Path(google_photos_takeout_model.__name__).with_suffix(".log"),
        level=logging.DEBUG,
    )
    for warning in [ResourceWarning, RuntimeWarning]:
        simplefilter("error", warning)
run(
    args=[
        executable,
        *(["-X", "frozen_modules=off"] if environ.get("DEBUGPY_RUNNING") else []),
        Path(files(google_photos_takeout_model))  # pyright: ignore[reportArgumentType]
        / f"{'clear_albums' if CLEAR else 'get_media_metadata'}{'2' if ALT and not CLEAR else ''}.py",
        *loads(albums.read_text(encoding="utf-8")),
    ],
    check=False,
)
