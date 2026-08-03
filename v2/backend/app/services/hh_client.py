"""HeadHunter API client (employer token, cold search without opening contacts)."""

from __future__ import annotations

import json
import time
from typing import Any

import requests

from app.core.config import Settings

HH_TOKEN_URL = "https://hh.ru/oauth/token"


class HhApiError(RuntimeError):
    def __init__(self, message: str, *, status: int | None = None, body: str = ""):
        super().__init__(message)
        self.status = status
        self.body = body


def _oauth_error_value(body: str) -> str | None:
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return None
    for err in data.get("errors") or []:
        if isinstance(err, dict) and err.get("type") == "oauth":
            return str(err.get("value") or "")
    return data.get("oauth_error")


def refresh_hh_access_token(settings: Settings) -> str:
    refresh = (settings.hh_refresh_token or "").strip()
    client_id = (settings.hh_client_id or "").strip()
    client_secret = (settings.hh_client_secret or "").strip()
    if not refresh:
        raise HhApiError(
            "HH access token истёк. Задайте HH_REFRESH_TOKEN или получите новую пару "
            "через scripts/hh_oauth.py"
        )
    if not client_id or not client_secret:
        raise HhApiError(
            "Для обновления токена нужны HH_CLIENT_ID и HH_CLIENT_SECRET в .env"
        )
    try:
        resp = requests.post(
            HH_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )
    except requests.RequestException as exc:
        raise HhApiError(f"HH refresh сеть: {exc}") from exc
    if resp.status_code >= 400:
        raise HhApiError(
            f"HH refresh {resp.status_code}: {resp.text[:400]}",
            status=resp.status_code,
            body=resp.text[:1000],
        )
    access = (resp.json().get("access_token") or "").strip()
    if not access:
        raise HhApiError("HH refresh: в ответе нет access_token")
    return access


class HhClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        token = (settings.hh_access_token or "").strip()
        if not token:
            raise HhApiError(
                "Не задан HH_ACCESS_TOKEN (токен менеджера работодателя). "
                "Добавьте в корневой .env или v2/.env."
            )
        self.base = (settings.hh_api_base or "https://api.hh.ru").rstrip("/")
        self.session = requests.Session()
        ua = (settings.hh_user_agent or "HR_AI_Agent_v2/1.0").strip()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "User-Agent": ua,
                "HH-User-Agent": ua,
            }
        )

    def _set_access_token(self, token: str) -> None:
        self.session.headers["Authorization"] = f"Bearer {token}"

    def _get(self, path: str, *, params: dict | None = None, _retried: bool = False) -> Any:
        url = f"{self.base}{path}"
        try:
            resp = self.session.get(url, params=params or {}, timeout=60)
        except requests.RequestException as exc:
            raise HhApiError(f"HH сеть: {exc}") from exc
        if resp.status_code >= 400:
            oauth_err = _oauth_error_value(resp.text[:1000])
            if not _retried and resp.status_code == 403 and oauth_err == "token_expired":
                new_token = refresh_hh_access_token(self.settings)
                self._set_access_token(new_token)
                return self._get(path, params=params, _retried=True)
            raise HhApiError(
                f"HH API {resp.status_code}: {resp.text[:400]}",
                status=resp.status_code,
                body=resp.text[:1000],
            )
        return resp.json()

    def search_resumes(
        self,
        text: str,
        *,
        page: int = 0,
        per_page: int = 20,
        area: int | None = None,
        schedule: str | None = None,
        salary_to: int | None = None,
        period: int | None = None,
        extra_params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "text": text,
            "page": page,
            "per_page": min(50, max(1, per_page)),
        }
        if area is not None:
            params["area"] = area
        if schedule:
            params["schedule"] = schedule
        if salary_to is not None:
            params["salary_to"] = salary_to
        if period is not None:
            params["period"] = max(1, min(365, int(period)))
        if extra_params:
            params.update(extra_params)
        return self._get("/resumes", params=params)

    def get_resume(self, resume_id: str) -> dict[str, Any]:
        """Full resume. Contacts stay null until actions.open_contacts is called (we never call it)."""
        rid = (resume_id or "").strip()
        if not rid:
            raise HhApiError("Пустой resume_id")
        return self._get(f"/resumes/{rid}")


def search_resume_items(
    client: HhClient,
    keywords: str,
    *,
    max_items: int = 20,
    per_page: int = 20,
    pause_s: float = 0.35,
    area: int | None = None,
    schedule: str | None = None,
    salary_to: int | None = None,
    period: int | None = None,
    extra_params: dict[str, Any] | None = None,
    prioritized: bool = True,
) -> list[dict[str, Any]]:
    from app.services.hh_prefilter import query_quotas, split_queries

    keywords = (keywords or "").strip()
    if not keywords:
        raise HhApiError("Пустые ключевые слова для поиска")
    queries = split_queries(keywords)
    quotas = query_quotas(len(queries), max_items) if prioritized else [max_items] * len(queries)

    seen: set[str] = set()
    collected: list[dict[str, Any]] = []

    def _pull(q: str, rank: int, limit: int) -> None:
        nonlocal collected
        if limit <= 0:
            return
        got = 0
        page = 0
        while got < limit and len(collected) < max_items:
            batch = min(per_page, limit - got, max_items - len(collected))
            data = client.search_resumes(
                q,
                page=page,
                per_page=batch,
                area=area,
                schedule=schedule,
                salary_to=salary_to,
                period=period,
                extra_params=extra_params,
            )
            items = data.get("items") or []
            if not items:
                break
            for item in items:
                rid = str(item.get("id") or "")
                if rid and rid in seen:
                    continue
                if rid:
                    seen.add(rid)
                tagged = dict(item)
                tagged["_source_query"] = q
                tagged["_source_rank"] = rank
                collected.append(tagged)
                got += 1
                if got >= limit or len(collected) >= max_items:
                    break
            pages = int(data.get("pages") or 1)
            if page >= pages - 1:
                break
            page += 1
            time.sleep(pause_s)

    # Pass 1: per-query quotas (earlier lines get more slots)
    for rank, (q, quota) in enumerate(zip(queries, quotas)):
        _pull(q, rank, quota)
        time.sleep(pause_s)

    # Pass 2: backfill shortfall in query priority order
    if len(collected) < max_items:
        for rank, q in enumerate(queries):
            if len(collected) >= max_items:
                break
            _pull(q, rank, max_items - len(collected))
            time.sleep(pause_s)

    return collected[:max_items]
