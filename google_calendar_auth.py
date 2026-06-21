#!/usr/bin/env python3
"""Однократная авторизация Google Calendar (откроется браузер)."""

import sys

from google_calendar import run_oauth_authorization, run_oauth_console


if __name__ == "__main__":
    if "--console" in sys.argv:
        ok, msg = run_oauth_console()
    else:
        ok, msg = run_oauth_authorization()
    print(msg)
    raise SystemExit(0 if ok else 1)
