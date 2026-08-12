"""Candidate offer draft: prefill, AI assist, persist in payload.offer."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.config import Settings, get_settings
from app.db import models
from app.services.ai_json import chat_json
from app.services.candidate_fields import normalize_gender, payload_get

OFFER_KEYS = (
    "greeting",
    "name_patronymic",
    "full_name",
    "company",
    "position",
    "office_address",
    "work_schedule",
    "start_date",
    "probation_months",
    "salary_probation_base",
    "salary_probation_bonus",
    "salary_probation_line",
    "salary_after_base",
    "salary_after_bonus",
    "salary_after_line",
    "duties",
    "manager_name",
)

AI_SYSTEM = """Ты помощник рекрутера. По документам вакансии заполни фрагменты оффера.
Верни JSON:
{
  "work_schedule": "один абзац про режим дня БЕЗ слов «гибрид» и «удалёнка»; если в данных нет режима — пустая строка",
  "duties": "5–8 пунктов обязанностей, каждый с новой строки, начиная с «• »; только из профиля/текста вакансии, без выдумок",
  "office_address": "адрес офиса если явно есть в текстах, иначе пустая строка",
  "manager_name": "ФИО руководителя если явно есть, иначе пустая строка"
}
Пиши по-русски. Не выдумывай зарплаты и даты.
"""


def empty_offer() -> dict[str, str]:
    return {k: "" for k in OFFER_KEYS}


def _s(v: Any) -> str:
    return str(v or "").strip()


def months_word(n: int) -> str:
    n_abs = abs(n) % 100
    n1 = n_abs % 10
    if 11 <= n_abs <= 19:
        return "месяцев"
    if n1 == 1:
        return "месяц"
    if 2 <= n1 <= 4:
        return "месяца"
    return "месяцев"


def format_probation_months(raw: str) -> str:
    """Число → «3 месяца»; готовая формулировка остаётся как есть."""
    s = _s(raw)
    if not s:
        return ""
    if re.search(r"месяц", s, re.I):
        return s
    m = re.match(r"^(\d+)\s*$", s)
    if m:
        n = int(m.group(1))
        return f"{n} {months_word(n)}"
    return s


def compose_pay_line(base: str, bonus: str) -> str:
    b = _s(base)
    bonus_s = _s(bonus)
    if b and bonus_s:
        if bonus_s.startswith("+"):
            return f"{b} {bonus_s}"
        return f"{b} + {bonus_s}"
    return b or bonus_s


def split_name_parts(full_name: str) -> tuple[str, str]:
    """Return (name_patronymic, full_name_normalized)."""
    parts = [p for p in re.split(r"\s+", _s(full_name)) if p]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], parts[0]
    if len(parts) == 2:
        # Surname Name → name only for greeting; full as-is
        return parts[1], " ".join(parts)
    # Surname Name Patronymic
    return f"{parts[1]} {parts[2]}", " ".join(parts)


def greeting_for_gender(gender: str | None) -> str:
    g = normalize_gender(gender)
    if g == "female":
        return "Уважаемая"
    if g == "male":
        return "Уважаемый"
    return "Уважаемый(ая)"


def get_offer_draft(candidate: models.Candidate) -> dict[str, str]:
    raw = (candidate.payload or {}).get("offer")
    out = empty_offer()
    if isinstance(raw, dict):
        for k in OFFER_KEYS:
            if k in raw and raw[k] is not None:
                out[k] = _s(raw[k])
    return out


def normalize_offer_payload(data: dict[str, Any] | None) -> dict[str, str]:
    out = empty_offer()
    src = data or {}
    for k in OFFER_KEYS:
        if k in src and src[k] is not None:
            out[k] = _s(src[k])
    # Recompose lines if bases/bonuses present and line empty or stale request
    if out["salary_probation_base"] or out["salary_probation_bonus"]:
        if not out["salary_probation_line"] or src.get("_recompose_pay"):
            out["salary_probation_line"] = compose_pay_line(
                out["salary_probation_base"], out["salary_probation_bonus"]
            )
    if out["salary_after_base"] or out["salary_after_bonus"]:
        if not out["salary_after_line"] or src.get("_recompose_pay"):
            out["salary_after_line"] = compose_pay_line(
                out["salary_after_base"], out["salary_after_bonus"]
            )
    return out


def resolve_company_client(db: Session, vacancy: models.Vacancy | None) -> models.Client | None:
    if not vacancy or vacancy.client_id is None:
        return None
    client = db.get(models.Client, vacancy.client_id)
    if not client:
        return None
    # Prefer company root for logo/address defaults
    if client.parent_id is not None:
        parent = db.get(models.Client, client.parent_id)
        if parent:
            return parent
    return client


def prefill_offer_draft(db: Session, candidate: models.Candidate) -> dict[str, str]:
    """Build draft from existing app data (does not invent salary/bonus)."""
    existing = get_offer_draft(candidate)
    vacancy = db.get(models.Vacancy, candidate.vacancy_id)
    company = resolve_company_client(db, vacancy)
    p = dict(candidate.payload or {})

    full = _s(candidate.name) or existing["full_name"]
    name_pat, full_norm = split_name_parts(full)
    gender = normalize_gender(payload_get(p, "gender", "sex"))

    draft = empty_offer()
    draft["greeting"] = existing["greeting"] or greeting_for_gender(gender)
    draft["name_patronymic"] = existing["name_patronymic"] or name_pat
    draft["full_name"] = existing["full_name"] or full_norm or full
    draft["company"] = existing["company"] or _s(company.name if company else "")
    if not draft["company"] and vacancy and vacancy.client_id is not None:
        leaf = db.get(models.Client, vacancy.client_id)
        draft["company"] = _s(leaf.name if leaf else "")
    draft["position"] = existing["position"] or _s(vacancy.title if vacancy else "")
    draft["office_address"] = existing["office_address"] or _s(
        (company.payload or {}).get("office_address") if company else ""
    )
    draft["work_schedule"] = existing["work_schedule"]
    draft["start_date"] = existing["start_date"] or _fmt_display_date(
        payload_get(p, "warranty_start_date", "offer_date", "start_date")
    )
    draft["probation_months"] = existing["probation_months"]
    draft["salary_probation_base"] = existing["salary_probation_base"]
    draft["salary_probation_bonus"] = existing["salary_probation_bonus"]
    draft["salary_after_base"] = existing["salary_after_base"]
    draft["salary_after_bonus"] = existing["salary_after_bonus"]
    # Optionally seed base from expected salary once
    expected = _s(payload_get(p, "salary_expected", "salary"))
    if expected and not draft["salary_probation_base"] and not draft["salary_after_base"]:
        # Soft hint only into base fields — recruiter edits «на руки» wording
        draft["salary_probation_base"] = expected
        draft["salary_after_base"] = expected
    draft["salary_probation_line"] = existing["salary_probation_line"] or compose_pay_line(
        draft["salary_probation_base"], draft["salary_probation_bonus"]
    )
    draft["salary_after_line"] = existing["salary_after_line"] or compose_pay_line(
        draft["salary_after_base"], draft["salary_after_bonus"]
    )
    draft["duties"] = existing["duties"]
    draft["manager_name"] = existing["manager_name"] or _s(
        (company.payload or {}).get("offer_manager_name") if company else ""
    )
    draft["work_schedule"] = existing["work_schedule"] or _s(
        (company.payload or {}).get("default_work_schedule") if company else ""
    )
    return draft


def _fmt_display_date(raw: Any) -> str:
    s = _s(raw)
    if not s:
        return ""
    if re.match(r"^\d{4}-\d{2}-\d{2}", s):
        try:
            from datetime import date

            d = date.fromisoformat(s[:10])
            return d.strftime("%d.%m.%Y")
        except ValueError:
            return s
    return s


def save_offer_draft(db: Session, candidate: models.Candidate, data: dict[str, Any]) -> dict[str, str]:
    draft = normalize_offer_payload({**get_offer_draft(candidate), **(data or {}), "_recompose_pay": True})
    payload = dict(candidate.payload or {})
    payload["offer"] = {
        **draft,
        "updated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }
    candidate.payload = payload
    flag_modified(candidate, "payload")
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return draft


def ai_fill_offer_fields(
    db: Session,
    candidate: models.Candidate,
    *,
    settings: Settings | None = None,
) -> dict[str, str]:
    settings = settings or get_settings()
    vacancy = db.get(models.Vacancy, candidate.vacancy_id)
    docs = (vacancy.documents or {}) if vacancy else {}
    profile = _s(docs.get("profile"))
    vtext = _s(docs.get("vacancy_text"))
    notes = _s(docs.get("notes"))
    questions = _s(docs.get("questions"))
    if not (profile or vtext or notes or questions):
        raise ValueError("В документах вакансии нет текста для ИИ (профиль / текст вакансии)")

    user = (
        f"Должность: {(vacancy.title if vacancy else '') or '—'}\n"
        f"Компания: {prefill_offer_draft(db, candidate).get('company') or '—'}\n\n"
        f"Профиль:\n{profile[:5000]}\n\n"
        f"Текст вакансии:\n{vtext[:5000]}\n\n"
        f"Заметки:\n{notes[:2000]}\n\n"
        f"Вопросы/опросник (для понимания обязанностей):\n{questions[:3000]}"
    )
    raw = chat_json(
        settings,
        system=AI_SYSTEM,
        user=user,
        temperature=0.3,
        max_tokens=2500,
        db=db,
        task="offer_ai_fill",
    )
    if not isinstance(raw, dict):
        raise RuntimeError("ИИ вернул неожиданный ответ")

    draft = get_offer_draft(candidate)
    if not draft.get("full_name"):
        draft = prefill_offer_draft(db, candidate)

    for key in ("work_schedule", "duties", "office_address", "manager_name"):
        val = _s(raw.get(key))
        if val:
            draft[key] = val
    return save_offer_draft(db, candidate, draft)


def company_logo_data_url(db: Session, vacancy: models.Vacancy | None) -> str | None:
    company = resolve_company_client(db, vacancy)
    if not company:
        return None
    url = _s((company.payload or {}).get("offer_logo_data_url"))
    return url or None
