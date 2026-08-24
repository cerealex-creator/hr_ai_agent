"""СУП — паспорт бизнеса (контекст для генерации целей)."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import management_models as m

INDUSTRY_OPTIONS: list[dict[str, str]] = [
    {"code": "retail", "label": "Розница / e-commerce"},
    {"code": "services", "label": "Услуги (B2B/B2C)"},
    {"code": "production", "label": "Производство"},
    {"code": "it", "label": "IT / digital"},
    {"code": "construction", "label": "Строительство / проекты"},
    {"code": "horeca", "label": "HoReCa"},
    {"code": "other", "label": "Другое"},
]

BUSINESS_MODEL_OPTIONS = [
    {"code": "product", "label": "Продукт"},
    {"code": "service", "label": "Услуга"},
    {"code": "hybrid", "label": "Продукт + услуга"},
]

MARKET_TYPE_OPTIONS = [
    {"code": "b2b", "label": "B2B"},
    {"code": "b2c", "label": "B2C"},
    {"code": "mixed", "label": "Смешанная модель"},
]

SCALE_BAND_OPTIONS = [
    {"code": "micro", "label": "До 5 человек"},
    {"code": "small", "label": "5–20 человек"},
    {"code": "medium", "label": "20–100 человек"},
    {"code": "large", "label": "100+ человек"},
]

MATURITY_OPTIONS = [
    {"code": "startup", "label": "Старт / запуск"},
    {"code": "growth", "label": "Рост"},
    {"code": "stable", "label": "Стабильная работа"},
    {"code": "turnaround", "label": "Перестройка / кризис"},
]

HORIZON_OPTIONS = [
    {"months": 6, "label": "6 месяцев"},
    {"months": 12, "label": "12 месяцев"},
    {"months": 18, "label": "18 месяцев"},
    {"months": 24, "label": "24 месяца"},
]

PRIORITY_OPTIONS = [
    {"code": "revenue", "label": "Выручка и продажи"},
    {"code": "profit", "label": "Прибыль и маржа"},
    {"code": "clients", "label": "Клиенты и удержание"},
    {"code": "quality", "label": "Качество и процессы"},
    {"code": "team", "label": "Команда и найм"},
    {"code": "stability", "label": "Стабильность и риски"},
]


def business_profile_schema() -> dict:
    return {
        "industries": INDUSTRY_OPTIONS,
        "business_models": BUSINESS_MODEL_OPTIONS,
        "market_types": MARKET_TYPE_OPTIONS,
        "scale_bands": SCALE_BAND_OPTIONS,
        "maturity_stages": MATURITY_OPTIONS,
        "horizons": HORIZON_OPTIONS,
        "priorities": PRIORITY_OPTIONS,
    }


def get_business_profile(db: Session, revision_id: uuid.UUID) -> m.MgmtBusinessProfile | None:
    return db.scalar(
        select(m.MgmtBusinessProfile).where(m.MgmtBusinessProfile.revision_id == revision_id)
    )


def get_or_create_business_profile(db: Session, revision_id: uuid.UUID) -> m.MgmtBusinessProfile:
    profile = get_business_profile(db, revision_id)
    if profile:
        return profile
    profile = m.MgmtBusinessProfile(revision_id=revision_id, status="draft")
    db.add(profile)
    db.flush()
    return profile


def save_business_profile(
    db: Session,
    revision_id: uuid.UUID,
    *,
    industry_code: str | None = None,
    industry_custom: str | None = None,
    business_model: str | None = None,
    market_type: str | None = None,
    scale_band: str | None = None,
    maturity_stage: str | None = None,
    horizon_months: int | None = None,
    priorities: list[str] | None = None,
    constraints_text: str | None = None,
    sensitive_metrics_opt_out: bool | None = None,
    optional_metrics: dict | None = None,
) -> m.MgmtBusinessProfile:
    profile = get_or_create_business_profile(db, revision_id)
    if industry_code is not None:
        profile.industry_code = industry_code.strip() or None
    if industry_custom is not None:
        profile.industry_custom = industry_custom.strip() or None
    if business_model is not None:
        profile.business_model = business_model.strip() or None
    if market_type is not None:
        profile.market_type = market_type.strip() or None
    if scale_band is not None:
        profile.scale_band = scale_band.strip() or None
    if maturity_stage is not None:
        profile.maturity_stage = maturity_stage.strip() or None
    if horizon_months is not None:
        profile.horizon_months = horizon_months
    if priorities is not None:
        profile.priorities = [p for p in priorities if p][:6]
    if constraints_text is not None:
        profile.constraints_text = constraints_text.strip() or None
    if sensitive_metrics_opt_out is not None:
        profile.sensitive_metrics_opt_out = sensitive_metrics_opt_out
    if optional_metrics is not None:
        profile.optional_metrics = optional_metrics
    db.flush()
    return profile


def validate_business_profile(profile: m.MgmtBusinessProfile | None) -> list[str]:
    if not profile:
        return ["BUSINESS_PROFILE_MISSING: заполните паспорт бизнеса"]
    errors: list[str] = []
    if not (profile.industry_code or (profile.industry_custom or "").strip()):
        errors.append("INDUSTRY_REQUIRED: укажите отрасль")
    if not profile.business_model:
        errors.append("BUSINESS_MODEL_REQUIRED: укажите модель бизнеса")
    if not profile.scale_band:
        errors.append("SCALE_REQUIRED: укажите масштаб")
    if not profile.horizon_months:
        errors.append("HORIZON_REQUIRED: укажите горизонт планирования")
    return errors


def profile_context_for_ai(profile: m.MgmtBusinessProfile | None) -> str:
    if not profile:
        return "Паспорт бизнеса не заполнен."
    industry = profile.industry_custom or profile.industry_code or "не указана"
    parts = [
        "## Паспорт бизнеса",
        f"- Отрасль: {industry}",
        f"- Модель: {profile.business_model or '—'}",
        f"- Рынок: {profile.market_type or '—'}",
        f"- Масштаб: {profile.scale_band or '—'}",
        f"- Стадия: {profile.maturity_stage or '—'}",
        f"- Горизонт: {profile.horizon_months or '—'} мес.",
    ]
    if profile.priorities:
        parts.append(f"- Приоритеты: {', '.join(profile.priorities)}")
    if profile.constraints_text:
        parts.append(f"- Ограничения: {profile.constraints_text}")
    if profile.sensitive_metrics_opt_out:
        parts.append("- Собственник предпочёл не указывать чувствительные цифры — цели без baseline/target допустимы.")
    metrics = profile.optional_metrics or {}
    disclosed = [
        f"{k}: {v.get('value')}"
        for k, v in metrics.items()
        if isinstance(v, dict) and v.get("disclosed") and v.get("value")
    ]
    if disclosed:
        parts.append(f"- Добровольно указанные метрики: {'; '.join(disclosed)}")
    return "\n".join(parts)


def mark_profile_complete(profile: m.MgmtBusinessProfile) -> None:
    profile.status = "complete"
