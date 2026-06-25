"""Секретные ссылки на клиентские зоны (без ?dept= в URL)."""

import json
import os
import secrets

from vacancy_store import DEPARTMENTS_FILE, DATA_DIR

ZONE_ACCESS_FILE = os.path.join(DATA_DIR, "zone_access.json")


def _read_departments_payload():
    if not os.path.exists(DEPARTMENTS_FILE):
        return {"departments": []}
    with open(DEPARTMENTS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return {"departments": data}
    return data


def _write_departments_payload(payload):
    os.makedirs(os.path.dirname(DEPARTMENTS_FILE) or ".", exist_ok=True)
    with open(DEPARTMENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def ensure_department_tokens():
    """Добавляет client_zone_token каждому отделу при отсутствии. Возвращает список отделов."""
    payload = _read_departments_payload()
    changed = False
    for dept in payload.get("departments", []):
        if not (dept.get("client_zone_token") or "").strip():
            dept["client_zone_token"] = secrets.token_urlsafe(32)
            changed = True
    if changed:
        _write_departments_payload(payload)
    return payload.get("departments", [])


def get_department_by_client_token(token):
    token = (token or "").strip()
    if not token:
        return None
    for dept in ensure_department_tokens():
        stored = (dept.get("client_zone_token") or "").strip()
        if stored and secrets.compare_digest(stored, token):
            return dept
    return None


def _read_zone_access():
    if not os.path.exists(ZONE_ACCESS_FILE):
        return {}
    with open(ZONE_ACCESS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_zone_access(data):
    os.makedirs(os.path.dirname(ZONE_ACCESS_FILE) or ".", exist_ok=True)
    with open(ZONE_ACCESS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_master_zone_token():
    from_env = (os.getenv("MASTER_ZONE_ACCESS_TOKEN") or "").strip()
    if from_env:
        return from_env
    data = _read_zone_access()
    token = (data.get("master_zone_token") or "").strip()
    if token:
        return token
    token = secrets.token_urlsafe(32)
    _write_zone_access({"master_zone_token": token})
    return token


def verify_master_zone_token(token):
    token = (token or "").strip()
    expected = get_master_zone_token()
    if not token or not expected:
        return False
    return secrets.compare_digest(expected, token)


def _public_base_url():
    return (os.getenv("PUBLIC_APP_BASE_URL") or "").strip().rstrip("/")


def build_client_zone_href(dept, *, vacancy_id=None, candidate_id=None):
    token = (dept.get("client_zone_token") or "").strip()
    if not token:
        for d in ensure_department_tokens():
            if d.get("id") == dept.get("id"):
                token = d.get("client_zone_token", "")
                break
    path = f"/client?t={token}"
    if vacancy_id is not None and str(vacancy_id).strip():
        path += f"&vacancy_id={vacancy_id}"
    if candidate_id is not None and str(candidate_id).strip():
        path += f"&candidate_id={candidate_id}"
    base = _public_base_url()
    return f"{base}{path}" if base else path


def build_client_candidate_href(dept, vacancy, candidate):
    """Прямая ссылка на карточку кандидата в client zone."""
    return build_client_zone_href(
        dept,
        vacancy_id=vacancy.get("id"),
        candidate_id=candidate.get("id"),
    )


def get_department_for_vacancy(vacancy):
    for dept in ensure_department_tokens():
        if dept.get("id") == vacancy.get("client_id"):
            return dept
    return None


def build_master_zone_href():
    path = f"/master?t={get_master_zone_token()}"
    base = _public_base_url()
    return f"{base}{path}" if base else path


def extract_access_token(query_params):
    """Токен из ?t= или ?token=."""
    if hasattr(query_params, "get"):
        return (query_params.get("t") or query_params.get("token") or "").strip()
    return ""
