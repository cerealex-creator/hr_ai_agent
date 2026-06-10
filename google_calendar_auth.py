#!/usr/bin/env python3
"""Однократная авторизация Google Calendar (откроется браузер)."""

from google_calendar import run_oauth_authorization

if __name__ == "__main__":
    ok, msg = run_oauth_authorization()
    print(msg)
    raise SystemExit(0 if ok else 1)
