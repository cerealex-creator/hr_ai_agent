#!/usr/bin/env python3
"""Получить HH access/refresh token (OAuth менеджера работодателя).

Использование из v2/backend:
  set -a && source ../../.env && set +a
  .venv/bin/python scripts/hh_oauth.py

После успеха токены пишутся в ``data/hh_oauth.json``; строки .env печатаются как запасной вариант.
Перезапустите API + ARQ worker.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import urlencode

import requests

ROOT = Path(__file__).resolve().parents[3]
ENV_PATH = ROOT / ".env"
TOKEN_URL = "https://hh.ru/oauth/token"
API_BASE = "https://api.hh.ru"


def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip())


def _require(name: str) -> str:
    val = (os.environ.get(name) or "").strip()
    if not val:
        print(f"Ошибка: не задан {name} в {ENV_PATH}", file=sys.stderr)
        sys.exit(1)
    return val


def _probe(token: str, user_agent: str) -> tuple[int, dict | None]:
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": user_agent,
        "HH-User-Agent": user_agent,
    }
    me = requests.get(f"{API_BASE}/me", headers=headers, timeout=30)
    if me.status_code != 200:
        return me.status_code, me.json() if me.headers.get("content-type", "").startswith("application/json") else None
    data = me.json()
    resumes = requests.get(
        f"{API_BASE}/resumes",
        headers=headers,
        params={"text": "python", "per_page": 1},
        timeout=30,
    )
    return resumes.status_code, {
        "is_employer": data.get("is_employer"),
        "is_applicant": data.get("is_applicant"),
        "employer_id": (data.get("employer") or {}).get("id") if isinstance(data.get("employer"), dict) else None,
        "resumes_status": resumes.status_code,
        "resumes_error": resumes.json().get("errors") if resumes.status_code >= 400 else None,
    }


def main() -> None:
    _load_dotenv(ENV_PATH)
    client_id = _require("HH_CLIENT_ID")
    client_secret = _require("HH_CLIENT_SECRET")
    redirect_uri = (os.environ.get("HH_REDIRECT_URI") or "").strip()
    user_agent = (os.environ.get("HH_USER_AGENT") or "HR_AI_Agent_v2/1.0 (dialex307@gmail.com)").strip()

    params = {"response_type": "code", "client_id": client_id}
    if redirect_uri:
        params["redirect_uri"] = redirect_uri
    auth_url = f"https://hh.ru/oauth/authorize?{urlencode(params)}"

    print("1) Откройте ссылку в браузере и войдите как менеджер работодателя:\n")
    print(auth_url)
    print("\n2) После редиректа скопируйте параметр code из URL (или весь URL).")
    raw = input("\nВставьте code или URL: ").strip()
    if "code=" in raw:
        from urllib.parse import parse_qs, urlparse

        q = parse_qs(urlparse(raw).query)
        code = (q.get("code") or [""])[0]
    else:
        code = raw
    if not code:
        print("Пустой code.", file=sys.stderr)
        sys.exit(1)

    body = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
    }
    if redirect_uri:
        body["redirect_uri"] = redirect_uri

    resp = requests.post(TOKEN_URL, data=body, timeout=30)
    if resp.status_code >= 400:
        print(f"Ошибка обмена code ({resp.status_code}): {resp.text}", file=sys.stderr)
        sys.exit(1)

    payload = resp.json()
    access = (payload.get("access_token") or "").strip()
    refresh = (payload.get("refresh_token") or "").strip()
    if not access:
        print("В ответе нет access_token.", file=sys.stderr)
        sys.exit(1)

    status, info = _probe(access, user_agent)
    print("\n--- Проверка токена ---")
    if info:
        print(f"  /me: employer={info.get('is_employer')} applicant={info.get('is_applicant')}")
        print(f"  /resumes: HTTP {info.get('resumes_status')}")
        if info.get("resumes_error"):
            print(f"  ошибка: {info.get('resumes_error')}")
    else:
        print(f"  /me: HTTP {status}")

    print("\n--- Добавьте в корневой .env (опционально; предпочтительно файл) ---\n")
    print(f"HH_ACCESS_TOKEN={access}")
    if refresh:
        print(f"HH_REFRESH_TOKEN={refresh}")
    print(f"HH_USER_AGENT={user_agent}")

    data_dir = Path(os.environ.get("LEGACY_DATA_DIR") or (ROOT / "data"))
    token_path = data_dir / "hh_oauth.json"
    try:
        from datetime import datetime, timezone

        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(
            __import__("json").dumps(
                {
                    "access_token": access,
                    "refresh_token": refresh,
                    "saved_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"\nТокены сохранены в {token_path} (приоритет над .env после refresh).")
    except Exception as exc:  # noqa: BLE001
        print(f"\nНе удалось записать {token_path}: {exc}", file=sys.stderr)

    print("\nЗатем перезапустите uvicorn и arq worker.")


if __name__ == "__main__":
    main()
