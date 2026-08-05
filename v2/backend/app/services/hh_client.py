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

    def _get(
        self,
        path: str,
        *,
        params: dict | list[tuple[str, Any]] | None = None,
        _retried: bool = False,
    ) -> Any:
        url = f"{self.base}{path}"
        try:
            resp = self.session.get(url, params=params if params is not None else {}, timeout=60)
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
        text_logic: str | None = None,
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
        logic = (text_logic or "").strip().lower()
        if logic in ("any", "all", "except", "phrase"):
            params["text.logic"] = logic
        if extra_params:
            params.update(extra_params)
        return self._get("/resumes", params=params)

    def search_resumes_params(
        self,
        base_params: list[tuple[str, Any]],
        *,
        page: int = 0,
        per_page: int = 20,
    ) -> dict[str, Any]:
        """GET /resumes with multi-value params (text triads, areas, roles, …)."""
        params: list[tuple[str, Any]] = list(base_params)
        params.append(("page", page))
        params.append(("per_page", min(50, max(1, per_page))))
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
    keywords_and: str = "",
    keywords_logic: str = "any",
    criteria: dict[str, Any] | None = None,
    extra_params: dict[str, Any] | None = None,
    prioritized: bool = True,
) -> list[dict[str, Any]]:
    from app.services.hh_prefilter import query_quotas
    from app.services.hh_search_criteria import build_hh_text_queries

    if criteria is not None:
        query_specs = build_hh_text_queries(criteria)
    else:
        query_specs = build_hh_text_queries(
            keywords=keywords,
            keywords_and=keywords_and,
            keywords_logic=keywords_logic,
        )
    if not query_specs:
        raise HhApiError("Пустые ключевые слова для поиска")

    quotas = (
        query_quotas(len(query_specs), max_items)
        if prioritized
        else [max_items] * len(query_specs)
    )

    seen: set[str] = set()
    collected: list[dict[str, Any]] = []

    def _pull(q: str, logic: str, rank: int, limit: int) -> None:
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
                text_logic=logic,
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
                tagged["_source_logic"] = logic
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

    for rank, (spec, quota) in enumerate(zip(query_specs, quotas)):
        _pull(spec["text"], spec.get("logic") or "any", rank, quota)
        time.sleep(pause_s)

    if len(collected) < max_items:
        for rank, spec in enumerate(query_specs):
            if len(collected) >= max_items:
                break
            _pull(spec["text"], spec.get("logic") or "any", rank, max_items - len(collected))
            time.sleep(pause_s)

    return collected[:max_items]


def search_resume_items_from_preset(
    client: HhClient,
    preset: dict[str, Any],
    *,
    max_items: int = 20,
    per_page: int = 20,
    pause_s: float = 0.35,
) -> list[dict[str, Any]]:
    """Cold search driven solely by hh_preset.api (exact HH params)."""
    from app.services.hh_preset import compile_hh_query_params, normalize_preset

    p = normalize_preset(preset)
    base = compile_hh_query_params(p)
    texts = [t for t in p["api"]["texts"] if (t.get("text") or "").strip()]
    if not texts:
        raise HhApiError("Пустые ключевые слова в пресете")

    # One HH call with all text triads + filters (mirrors HH UI multi-text).
    # If several OR synonym blocks are needed as separate queries later, split here.
    seen: set[str] = set()
    collected: list[dict[str, Any]] = []
    page = 0
    label = " · ".join(t["text"] for t in texts[:3])
    while len(collected) < max_items:
        batch = min(per_page, max_items - len(collected))
        data = client.search_resumes_params(base, page=page, per_page=batch)
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
            tagged["_source_query"] = label
            tagged["_source_logic"] = texts[0].get("logic") or "any"
            tagged["_source_rank"] = 0
            collected.append(tagged)
            if len(collected) >= max_items:
                break
        pages = int(data.get("pages") or 1)
        if page >= pages - 1:
            break
        page += 1
        time.sleep(pause_s)
    return collected[:max_items]
