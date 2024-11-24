from threading import Thread
from time import sleep

import pyautogui
from keyboard import is_pressed
from pyautogui import hotkey as h
from pyautogui import press as p

DEBUG = False
BATCH = 16
KILLSWITCH = "esc"
pyautogui.PAUSE = 0.5


def main():
    Thread(target=share_albums, daemon=True).start()
    while not is_pressed(KILLSWITCH):
        sleep(1e-3)


def share_albums():
    if DEBUG:
        while not sleep(1):
            print("hello")
    else:
        h("alt", "tab")
        for _ in range(BATCH):
            share_album()


def share_album():  # sourcery skip: extract-duplicate-method
    # Open share menu
    for _ in range(4):
        p("Tab")
    p("Enter")
    # Create link
    p("Tab")
    p("Enter")
    p("Tab")
    p("Tab")
    p("Enter")
    # Wait for link to be created
    sleep(5)
    # Open link
    h("Shift", "Tab")
    p("Enter")
    # Wait for redirect
    sleep(5)
    # Bookmark link
    h("Ctrl", "d")
    p("Enter")
    # Close new tab and original tab
    h("Ctrl", "w")
    h("Ctrl", "w")
    # Wait
    sleep(5)


if __name__ == "__main__":
    main()
