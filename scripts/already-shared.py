import subprocess

import pyautogui
from pyautogui import hotkey as h
from pyautogui import press as p
from pyautogui import typewrite as t

pyautogui.PAUSE = 0.3
EMAIL = subprocess.run(
    ["git", "config", "user.email"], capture_output=True, text=True, check=False
).stdout.strip()
h("alt", "tab")
for _ in range(8):
    for _ in range(7):
        p("Tab")
    p("Enter")
    t(EMAIL)
    p("Enter")
    p("Tab")
    p("Enter")
    h("Ctrl", "w")
