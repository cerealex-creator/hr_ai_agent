"""HH search preset: exact API params + soft screener rules (vacancy.documents)."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from app.services.hh_search_criteria import (
    AREA_PRESETS,
    DOC_KEY as CRITERIA_DOC_KEY,
    SCHEDULE_OPTIONS,
    ensure_portrait,
    normalize_criteria,
)

DOC_KEY = "hh_preset"

TEXT_LOGIC = ("any", "all", "phrase", "except")
TEXT_FIELDS = (
    "everywhere",
    "title",
    "education",
    "skills",
    "experience",
    "experience_company",
    "experience_position",
    "experience_description",
)
TEXT_PERIODS = ("all_time", "last_year", "last_three_years")
EXPERIENCE_IDS = ("noExperience", "between1And3", "between3And6", "moreThan6")
EMPLOYMENT_IDS = ("full", "part", "project", "volunteer", "probation")
SCHEDULE_IDS = ("fullDay", "shift", "flexible", "remote", "flyInFlyOut")
EDUCATION_IDS = (
    "secondary",
    "special_secondary",
    "unfinished_higher",
    "higher",
    "bachelor",
    "master",
    "candidate",
    "doctor",
)
RELOCATION_IDS = ("living_or_relocation", "living", "living_but_relocation", "relocation")
ORDER_BY_IDS = ("relevance", "publication_time", "salary_desc", "salary_asc")
LABEL_IDS = (
    "only_with_photo",
    "only_with_salary",
    "only_with_age",
    "only_with_gender",
    "only_with_vehicle",
)
GENDER_IDS = ("male", "female")
OFFICE_REQUIRED = ("first_3_months", "always", "no")
PRESET_STATUS = ("draft", "approved")


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _lines(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    if isinstance(value, str):
        return [p.strip() for p in value.replace("|", "\n").splitlines() if p.strip()]
    return []


def _int_or_none(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _str_list(value: Any, *, allowed: tuple[str, ...] | None = None) -> list[str]:
    if isinstance(value, list):
        items = [str(x).strip() for x in value if str(x).strip()]
    elif isinstance(value, str) and value.strip():
        items = [value.strip()]
    else:
        items = []
    if allowed is None:
        return items
    allow = set(allowed)
    return [x for x in items if x in allow]


def _id_list(value: Any) -> list[int]:
    out: list[int] = []
    raw = value if isinstance(value, list) else ([value] if value not in (None, "") else [])
    for item in raw:
        n = _int_or_none(item)
        if n is not None and n not in out:
            out.append(n)
    return out


def empty_text_block() -> dict[str, str]:
    return {
        "text": "",
        "logic": "any",
        "field": "everywhere",
        "period": "all_time",
    }


def empty_api() -> dict[str, Any]:
    return {
        "texts": [empty_text_block()],
        "area_ids": [],
        "area_name": "",
        "relocation": "living_or_relocation",
        "professional_role_ids": [],
        "experience": [],
        "employment": [],
        "schedule": [],
        "education_level": [],
        "age_from": None,
        "age_to": None,
        "gender": None,
        "salary_from": None,
        "salary_to": None,
        "currency": "RUR",
        "period_days": 7,
        "order_by": "relevance",
        "label": [],
        "language": [],
        "driver_license_types": [],
        "by_text_prefix": False,
    }


def empty_soft() -> dict[str, Any]:
    return {
        "must_have": [],
        "reject": [],
        "title_priority": [],
        "portrait": {"hard": [], "important": [], "nice": []},
        "office_address": "",
        "max_commute_min": 60,
        "office_required": "no",
        "recruiter_comment": "",
        "soft_rules": {"ignore": [], "focus": [], "extra_stop": []},
    }


def empty_run() -> dict[str, Any]:
    return {
        "max_search": 40,
        "max_evaluate": 15,
        "smart_prefilter": True,
    }


def empty_preset() -> dict[str, Any]:
    return {
        "version": 1,
        "status": "draft",
        "api": empty_api(),
        "soft": empty_soft(),
        "run": empty_run(),
        "meta": {
            "created_at": None,
            "updated_at": None,
            "approved_at": None,
            "migrated_from": None,
            "prefilled_at": None,
            "sources": [],
        },
    }


def _normalize_text_block(raw: Any) -> dict[str, str] | None:
    if not isinstance(raw, dict):
        return None
    text = str(raw.get("text") or "").strip()
    if not text:
        return None
    logic = str(raw.get("logic") or "any").strip().lower()
    if logic not in TEXT_LOGIC:
        logic = "any"
    field = str(raw.get("field") or "everywhere").strip().lower()
    if field not in TEXT_FIELDS:
        field = "everywhere"
    period = str(raw.get("period") or "all_time").strip().lower()
    if period not in TEXT_PERIODS:
        period = "all_time"
    return {"text": text, "logic": logic, "field": field, "period": period}


def normalize_api(raw: Any) -> dict[str, Any]:
    base = empty_api()
    if not isinstance(raw, dict):
        return base
    data = deepcopy(base)
    texts: list[dict[str, str]] = []
    for item in raw.get("texts") or []:
        block = _normalize_text_block(item)
        if block:
            texts.append(block)
    data["texts"] = texts or [empty_text_block()]
    data["area_ids"] = _id_list(raw.get("area_ids") or raw.get("area_id"))
    data["area_name"] = str(raw.get("area_name") or "").strip()
    if not data["area_name"] and data["area_ids"]:
        aid = data["area_ids"][0]
        data["area_name"] = next((a["name"] for a in AREA_PRESETS if a["id"] == aid), "")
    reloc = str(raw.get("relocation") or "living_or_relocation").strip()
    data["relocation"] = reloc if reloc in RELOCATION_IDS else "living_or_relocation"
    data["professional_role_ids"] = _id_list(raw.get("professional_role_ids"))
    data["experience"] = _str_list(raw.get("experience"), allowed=EXPERIENCE_IDS)
    data["employment"] = _str_list(raw.get("employment"), allowed=EMPLOYMENT_IDS)
    data["schedule"] = _str_list(raw.get("schedule"), allowed=SCHEDULE_IDS)
    data["education_level"] = _str_list(raw.get("education_level"), allowed=EDUCATION_IDS)
    data["age_from"] = _int_or_none(raw.get("age_from"))
    data["age_to"] = _int_or_none(raw.get("age_to"))
    if data["age_from"] is not None:
        data["age_from"] = max(14, min(100, data["age_from"]))
    if data["age_to"] is not None:
        data["age_to"] = max(14, min(100, data["age_to"]))
    gender = raw.get("gender")
    gender_s = str(gender).strip().lower() if gender not in (None, "") else None
    data["gender"] = gender_s if gender_s in GENDER_IDS else None
    data["salary_from"] = _int_or_none(raw.get("salary_from"))
    data["salary_to"] = _int_or_none(raw.get("salary_to"))
    currency = str(raw.get("currency") or "RUR").strip().upper() or "RUR"
    data["currency"] = currency
    period = _int_or_none(raw.get("period_days"))
    data["period_days"] = max(1, min(365, period)) if period is not None else None
    order = str(raw.get("order_by") or "relevance").strip()
    data["order_by"] = order if order in ORDER_BY_IDS else "relevance"
    data["label"] = _str_list(raw.get("label"), allowed=LABEL_IDS)
    data["language"] = _lines(raw.get("language"))
    data["driver_license_types"] = [
        x.upper() for x in _lines(raw.get("driver_license_types")) if len(x) <= 3
    ]
    data["by_text_prefix"] = bool(raw.get("by_text_prefix"))
    return data


def normalize_soft(raw: Any) -> dict[str, Any]:
    base = empty_soft()
    if not isinstance(raw, dict):
        return base
    data = deepcopy(base)
    data["must_have"] = _lines(raw.get("must_have"))
    data["reject"] = _lines(raw.get("reject"))
    data["title_priority"] = _lines(raw.get("title_priority"))
    portrait_raw = raw.get("portrait") if isinstance(raw.get("portrait"), dict) else {}
    data["portrait"] = {
        "hard": _lines(portrait_raw.get("hard")),
        "important": _lines(portrait_raw.get("important")),
        "nice": _lines(portrait_raw.get("nice")),
    }
    data["office_address"] = str(raw.get("office_address") or "").strip()
    data["max_commute_min"] = _int_or_none(raw.get("max_commute_min")) or 60
    office = str(raw.get("office_required") or "no").strip()
    data["office_required"] = office if office in OFFICE_REQUIRED else "no"
    data["recruiter_comment"] = str(raw.get("recruiter_comment") or "").strip()
    soft = raw.get("soft_rules") if isinstance(raw.get("soft_rules"), dict) else {}
    data["soft_rules"] = {
        "ignore": _lines(soft.get("ignore")),
        "focus": _lines(soft.get("focus")),
        "extra_stop": _lines(soft.get("extra_stop")),
    }
    return data


def normalize_run(raw: Any) -> dict[str, Any]:
    base = empty_run()
    if not isinstance(raw, dict):
        return base
    data = deepcopy(base)
    data["max_search"] = max(1, min(50, _int_or_none(raw.get("max_search")) or 40))
    data["max_evaluate"] = max(0, min(50, _int_or_none(raw.get("max_evaluate")) or 15))
    data["max_evaluate"] = min(data["max_evaluate"], data["max_search"])
    if "smart_prefilter" in raw:
        data["smart_prefilter"] = bool(raw.get("smart_prefilter"))
    return data


def normalize_preset(raw: Any) -> dict[str, Any]:
    base = empty_preset()
    if not isinstance(raw, dict):
        return base
    data = deepcopy(base)
    data["version"] = 1
    status = str(raw.get("status") or "draft").strip().lower()
    data["status"] = status if status in PRESET_STATUS else "draft"
    data["api"] = normalize_api(raw.get("api") if isinstance(raw.get("api"), dict) else raw)
    # If caller sent flat soft fields at top-level (migration helpers), merge.
    soft_src = raw.get("soft") if isinstance(raw.get("soft"), dict) else {}
    if not soft_src and any(k in raw for k in ("must_have", "reject", "portrait", "recruiter_comment")):
        soft_src = raw
    data["soft"] = normalize_soft(soft_src)
    run_src = raw.get("run") if isinstance(raw.get("run"), dict) else {}
    if not run_src and any(k in raw for k in ("max_search", "max_evaluate", "smart_prefilter")):
        run_src = raw
    data["run"] = normalize_run(run_src)
    meta_raw = raw.get("meta") if isinstance(raw.get("meta"), dict) else {}
    data["meta"] = {
        "created_at": meta_raw.get("created_at") or raw.get("created_at"),
        "updated_at": meta_raw.get("updated_at") or raw.get("updated_at"),
        "approved_at": meta_raw.get("approved_at") or raw.get("approved_at"),
        "migrated_from": meta_raw.get("migrated_from"),
        "prefilled_at": meta_raw.get("prefilled_at"),
        "sources": list(meta_raw.get("sources") or [])
        if isinstance(meta_raw.get("sources"), list)
        else [],
    }
    return data


def experience_from_years(years: int | None) -> list[str]:
    if years is None:
        return []
    if years <= 0:
        return ["noExperience"]
    if years < 3:
        return ["between1And3", "between3And6", "moreThan6"]
    if years < 6:
        return ["between3And6", "moreThan6"]
    return ["moreThan6"]


def preset_from_criteria(criteria: dict[str, Any] | None) -> dict[str, Any]:
    """Best-effort migration from legacy hh_search_criteria."""
    c = normalize_criteria(criteria or {})
    preset = empty_preset()
    api = preset["api"]
    soft = preset["soft"]
    run = preset["run"]

    keywords = str(c.get("keywords") or "").strip()
    keywords_and = str(c.get("keywords_and") or "").strip()
    logic = str(c.get("keywords_logic") or "any").strip().lower()
    if logic not in TEXT_LOGIC:
        logic = "any"
    texts: list[dict[str, str]] = []
    if keywords:
        # Prefer one OR block; AND terms appended with logic=all when present.
        if keywords_and:
            for line in _lines(keywords) or [keywords]:
                texts.append(
                    {
                        "text": f"{line} {keywords_and}".strip(),
                        "logic": "all",
                        "field": "everywhere",
                        "period": "all_time",
                    }
                )
        else:
            or_join = " ".join(_lines(keywords)) or keywords
            texts.append(
                {
                    "text": or_join,
                    "logic": "any" if "\n" in keywords or logic == "any" else logic,
                    "field": "everywhere",
                    "period": "all_time",
                }
            )
    api["texts"] = texts or [empty_text_block()]
    if c.get("area_id") is not None:
        api["area_ids"] = [int(c["area_id"])]
    api["area_name"] = str(c.get("area_name") or "")
    schedule = str(c.get("schedule") or "").strip()
    # Legacy used schedule as hard HH filter; new default is empty (any).
    # Keep only if recruiter explicitly had one — but product decision was to stop
    # sending schedule. Migrate into soft portrait instead (via soft fields).
    api["schedule"] = []
    api["experience"] = experience_from_years(c.get("experience_from"))
    api["salary_to"] = c.get("salary_to")
    api["period_days"] = c.get("period_days") if c.get("period_days") is not None else 7

    soft["must_have"] = list(c.get("must_have") or [])
    soft["reject"] = list(c.get("reject") or [])
    soft["title_priority"] = list(c.get("title_priority") or [])
    soft["portrait"] = {
        "hard": list((c.get("portrait") or {}).get("hard") or []),
        "important": list((c.get("portrait") or {}).get("important") or []),
        "nice": list((c.get("portrait") or {}).get("nice") or []),
    }
    soft["office_address"] = str(c.get("office_address") or "")
    soft["max_commute_min"] = int(c.get("max_commute_min") or 60)
    soft["office_required"] = str(c.get("office_required") or "no")
    soft["recruiter_comment"] = str(c.get("recruiter_comment") or "")
    soft["soft_rules"] = dict(c.get("soft_rules") or {"ignore": [], "focus": [], "extra_stop": []})
    if schedule:
        label = next((o["label"] for o in SCHEDULE_OPTIONS if o["id"] == schedule), schedule)
        soft["portrait"]["important"].append(f"Формат/график (мягко): {label}")

    run["max_search"] = int(c.get("max_search") or 40)
    run["max_evaluate"] = int(c.get("max_evaluate") or 15)
    run["smart_prefilter"] = bool(c.get("smart_prefilter", True))

    preset["api"] = normalize_api(api)
    preset["soft"] = normalize_soft(soft)
    preset["run"] = normalize_run(run)
    preset["status"] = "draft"
    preset["meta"]["migrated_from"] = "hh_search_criteria"
    preset["meta"]["updated_at"] = _now_iso()
    return normalize_preset(preset)


def ensure_soft_portrait(preset: dict[str, Any], *, rebuild: bool = False) -> dict[str, Any]:
    p = normalize_preset(preset)
    soft = p["soft"]
    has_any = any(soft["portrait"][k] for k in ("hard", "important", "nice"))
    if rebuild or not has_any:
        # Reuse criteria portrait builder via bridge
        bridge = criteria_view_from_preset(p)
        bridge = ensure_portrait(bridge, rebuild=True)
        soft["portrait"] = bridge["portrait"]
        p["soft"] = soft
    return p


def criteria_view_from_preset(preset: dict[str, Any]) -> dict[str, Any]:
    """Legacy-shaped criteria for prefilter / AI / debrief (not the HH API driver)."""
    p = normalize_preset(preset)
    api = p["api"]
    soft = p["soft"]
    run = p["run"]
    texts = [t for t in api["texts"] if (t.get("text") or "").strip()]
    keywords = "\n".join(t["text"] for t in texts)
    return normalize_criteria(
        {
            "keywords": keywords,
            "keywords_and": "",
            "keywords_logic": texts[0]["logic"] if texts else "any",
            "area_id": api["area_ids"][0] if api["area_ids"] else None,
            "area_name": api["area_name"],
            "schedule": api["schedule"][0] if api["schedule"] else "",
            "experience_from": None,
            "salary_to": api["salary_to"],
            "period_days": api["period_days"],
            "office_address": soft["office_address"],
            "max_commute_min": soft["max_commute_min"],
            "office_required": soft["office_required"],
            "title_priority": soft["title_priority"],
            "must_have": soft["must_have"],
            "reject": soft["reject"],
            "portrait": soft["portrait"],
            "recruiter_comment": soft["recruiter_comment"],
            "soft_rules": soft["soft_rules"],
            "max_search": run["max_search"],
            "max_evaluate": run["max_evaluate"],
            "smart_prefilter": run["smart_prefilter"],
            "prefill_meta": {
                "prefilled_at": (p.get("meta") or {}).get("prefilled_at"),
                "sources": (p.get("meta") or {}).get("sources") or [],
                "recruiter_edited": p.get("status") == "approved",
            },
        }
    )


def compile_hh_query_params(preset: dict[str, Any]) -> list[tuple[str, Any]]:
    """Flat multi-value query params for GET /resumes (requests params=list)."""
    api = normalize_api(normalize_preset(preset)["api"])
    params: list[tuple[str, Any]] = []
    texts = [t for t in api["texts"] if (t.get("text") or "").strip()]
    for t in texts:
        params.append(("text", t["text"]))
        params.append(("text.logic", t["logic"]))
        params.append(("text.field", t["field"]))
        params.append(("text.period", t["period"]))
    for aid in api["area_ids"]:
        params.append(("area", aid))
    if api["area_ids"] and api["relocation"]:
        params.append(("relocation", api["relocation"]))
    for rid in api["professional_role_ids"]:
        params.append(("professional_role", rid))
    for exp in api["experience"]:
        params.append(("experience", exp))
    for emp in api["employment"]:
        params.append(("employment", emp))
    for sch in api["schedule"]:
        params.append(("schedule", sch))
    for edu in api["education_level"]:
        params.append(("education_level", edu))
    if api["age_from"] is not None:
        params.append(("age_from", api["age_from"]))
    if api["age_to"] is not None:
        params.append(("age_to", api["age_to"]))
    if api["gender"]:
        params.append(("gender", api["gender"]))
    if api["salary_from"] is not None:
        params.append(("salary_from", api["salary_from"]))
    if api["salary_to"] is not None:
        params.append(("salary_to", api["salary_to"]))
    if api["salary_from"] is not None or api["salary_to"] is not None:
        params.append(("currency", api["currency"] or "RUR"))
    if api["period_days"] is not None:
        params.append(("period", api["period_days"]))
    if api["order_by"]:
        params.append(("order_by", api["order_by"]))
    for lab in api["label"]:
        params.append(("label", lab))
    for lang in api["language"]:
        params.append(("language", lang))
    for dl in api["driver_license_types"]:
        params.append(("driver_license_types", dl))
    if api["by_text_prefix"]:
        params.append(("by_text_prefix", "true"))
    return params


def describe_preset_query(preset: dict[str, Any]) -> str:
    p = normalize_preset(preset)
    api = p["api"]
    bits: list[str] = []
    for t in api["texts"]:
        if not t.get("text"):
            continue
        bits.append(f"«{t['text']}» [{t['logic']}/{t['field']}]")
    if api["area_ids"]:
        bits.append(f"area={api['area_ids']} ({api['area_name'] or '—'})")
    if api["professional_role_ids"]:
        bits.append(f"roles={api['professional_role_ids']}")
    if api["experience"]:
        bits.append(f"exp={api['experience']}")
    if api["period_days"]:
        bits.append(f"period={api['period_days']}d")
    if api["schedule"]:
        bits.append(f"schedule={api['schedule']}")
    return " · ".join(bits) if bits else "(пусто)"


def warnings_for_preset(preset: dict[str, Any]) -> list[dict[str, str]]:
    p = normalize_preset(preset)
    api = p["api"]
    soft = p["soft"]
    out: list[dict[str, str]] = []
    texts = [t for t in api["texts"] if (t.get("text") or "").strip()]
    if not texts:
        out.append(
            {
                "level": "warning",
                "code": "no_texts",
                "text": "Нет ключевых слов — HH вернёт пусто или огромный шум.",
            }
        )
    if not api["area_ids"]:
        out.append(
            {
                "level": "warning",
                "code": "no_area",
                "text": "Регион не задан — в выдачу попадут другие города.",
            }
        )
    if not api["professional_role_ids"]:
        out.append(
            {
                "level": "info",
                "code": "no_role",
                "text": "Нет профессиональной роли — стоит выбрать (напр. Казначей = 50).",
            }
        )
    if not api.get("period_days"):
        out.append(
            {
                "level": "info",
                "code": "no_period",
                "text": "Нет фильтра свежести — будут и «спящие» резюме.",
            }
        )
    if p["status"] != "approved":
        out.append(
            {
                "level": "info",
                "code": "not_approved",
                "text": "Пресет в статусе draft — можно править и сохранять; для авто-поиска позже нужен approved.",
            }
        )
    if not soft["must_have"] and not any(soft["portrait"].values()) and not soft["recruiter_comment"]:
        out.append(
            {
                "level": "info",
                "code": "thin_soft",
                "text": "Soft-правила пустые — ИИ будет оценивать только по профилю вакансии.",
            }
        )
    return out


def preset_from_vacancy_documents(documents: dict | None, *, title: str = "") -> dict[str, Any]:
    docs = documents or {}
    stored = docs.get(DOC_KEY)
    if isinstance(stored, dict) and (stored.get("api") or stored.get("texts") or stored.get("status")):
        p = normalize_preset(stored)
        # Seed title into empty text
        texts = p["api"]["texts"]
        if title and not any((t.get("text") or "").strip() for t in texts):
            p["api"]["texts"] = [
                {
                    "text": title.strip(),
                    "logic": "any",
                    "field": "everywhere",
                    "period": "all_time",
                }
            ]
            p = normalize_preset(p)
        return ensure_soft_portrait(p)

    # Migrate legacy criteria once (caller should persist)
    legacy = docs.get(CRITERIA_DOC_KEY)
    if isinstance(legacy, dict):
        p = preset_from_criteria(legacy)
        if title and not any((t.get("text") or "").strip() for t in p["api"]["texts"]):
            p["api"]["texts"] = [
                {
                    "text": title.strip(),
                    "logic": "any",
                    "field": "everywhere",
                    "period": "all_time",
                }
            ]
            p = normalize_preset(p)
        return ensure_soft_portrait(p)

    p = empty_preset()
    if title.strip():
        p["api"]["texts"] = [
            {
                "text": title.strip(),
                "logic": "any",
                "field": "everywhere",
                "period": "all_time",
            }
        ]
    return ensure_soft_portrait(normalize_preset(p))


def save_preset_to_documents(documents: dict | None, preset: dict[str, Any]) -> dict:
    docs = dict(documents or {})
    p = normalize_preset(preset)
    meta = dict(p.get("meta") or {})
    now = _now_iso()
    if not meta.get("created_at"):
        meta["created_at"] = now
    meta["updated_at"] = now
    p["meta"] = meta
    docs[DOC_KEY] = p
    # Keep legacy criteria in sync for old code paths (manual eval / soften)
    docs[CRITERIA_DOC_KEY] = criteria_view_from_preset(p)
    return docs


def approve_preset(preset: dict[str, Any]) -> dict[str, Any]:
    p = ensure_soft_portrait(normalize_preset(preset))
    texts = [t for t in p["api"]["texts"] if (t.get("text") or "").strip()]
    if not texts:
        raise ValueError("Нельзя утвердить пресет без ключевых слов")
    p["status"] = "approved"
    meta = dict(p.get("meta") or {})
    meta["approved_at"] = _now_iso()
    meta["updated_at"] = meta["approved_at"]
    p["meta"] = meta
    return p


def form_options() -> dict[str, Any]:
    return {
        "area_presets": AREA_PRESETS,
        "text_logic": [
            {"id": "any", "label": "Любое из слов"},
            {"id": "all", "label": "Все слова"},
            {"id": "phrase", "label": "Точная фраза"},
            {"id": "except", "label": "Кроме слов"},
        ],
        "text_fields": [
            {"id": "everywhere", "label": "Везде в резюме"},
            {"id": "title", "label": "В названии должности"},
            {"id": "education", "label": "В образовании"},
            {"id": "skills", "label": "В ключевых навыках"},
            {"id": "experience", "label": "В опыте работы"},
            {"id": "experience_company", "label": "В названии компаний"},
            {"id": "experience_position", "label": "В должностях опыта"},
            {"id": "experience_description", "label": "В описании опыта"},
        ],
        "text_periods": [
            {"id": "all_time", "label": "За всё время"},
            {"id": "last_year", "label": "За последний год"},
            {"id": "last_three_years", "label": "За 3 года"},
        ],
        "experience": [
            {"id": "noExperience", "label": "Нет опыта"},
            {"id": "between1And3", "label": "1–3 года"},
            {"id": "between3And6", "label": "3–6 лет"},
            {"id": "moreThan6", "label": "Более 6 лет"},
        ],
        "employment": [
            {"id": "full", "label": "Полная занятость"},
            {"id": "part", "label": "Частичная занятость"},
            {"id": "project", "label": "Проектная работа"},
            {"id": "volunteer", "label": "Волонтёрство"},
            {"id": "probation", "label": "Стажировка"},
        ],
        "schedule": [
            {"id": "fullDay", "label": "Полный день"},
            {"id": "shift", "label": "Сменный график"},
            {"id": "flexible", "label": "Гибкий график"},
            {"id": "remote", "label": "Удалённая работа"},
            {"id": "flyInFlyOut", "label": "Вахта"},
        ],
        "relocation": [
            {"id": "living_or_relocation", "label": "Живёт или готов переехать"},
            {"id": "living", "label": "Только живёт в регионе"},
            {"id": "living_but_relocation", "label": "Живёт и готов переехать"},
            {"id": "relocation", "label": "Только готов переехать"},
        ],
        "order_by": [
            {"id": "relevance", "label": "По соответствию"},
            {"id": "publication_time", "label": "По дате обновления"},
            {"id": "salary_desc", "label": "По убыванию зарплаты"},
            {"id": "salary_asc", "label": "По возрастанию зарплаты"},
        ],
        "education_level": [
            {"id": "secondary", "label": "Среднее"},
            {"id": "special_secondary", "label": "Среднее специальное"},
            {"id": "unfinished_higher", "label": "Неоконченное высшее"},
            {"id": "higher", "label": "Высшее"},
            {"id": "bachelor", "label": "Бакалавр"},
            {"id": "master", "label": "Магистр"},
            {"id": "candidate", "label": "Кандидат наук"},
            {"id": "doctor", "label": "Доктор наук"},
        ],
        "label": [
            {"id": "only_with_photo", "label": "Только с фото"},
            {"id": "only_with_salary", "label": "Только с зарплатой"},
            {"id": "only_with_age", "label": "Только с возрастом"},
            {"id": "only_with_gender", "label": "Только с полом"},
            {"id": "only_with_vehicle", "label": "Только с автомобилем"},
        ],
        "gender": [
            {"id": "male", "label": "Мужской"},
            {"id": "female", "label": "Женский"},
        ],
        "office_required": [
            {"id": "no", "label": "Не важно"},
            {"id": "first_3_months", "label": "Офис первые 3 мес."},
            {"id": "always", "label": "Постоянно в офисе"},
        ],
    }
