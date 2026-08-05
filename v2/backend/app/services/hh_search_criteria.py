"""HH search criteria: structure, portrait tiers, warnings (stored in vacancy.documents)."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Literal

from app.services.vacancy_docs import extract_keywords

Priority = Literal["hard", "important", "nice"]
PRIORITY_VALUES = ("hard", "important", "nice")

DOC_KEY = "hh_search_criteria"

SCHEDULE_OPTIONS = [
    {"id": "", "label": "Не задано"},
    {"id": "fullDay", "label": "Полный день (часто «на месте»)"},
    {"id": "flexible", "label": "Гибкий график"},
    {"id": "remote", "label": "Удалённая работа"},
    {"id": "shift", "label": "Сменный график"},
    {"id": "flyInFlyOut", "label": "Вахта"},
]

# Common HH area ids for quick pick
AREA_PRESETS = [
    {"id": 1, "name": "Москва"},
    {"id": 2, "name": "Санкт-Петербург"},
    {"id": 3, "name": "Екатеринбург"},
    {"id": 4, "name": "Новосибирск"},
    {"id": 88, "name": "Казань"},
    {"id": 66, "name": "Нижний Новгород"},
]


def _norm_priority(value: Any, default: Priority = "important") -> Priority:
    v = str(value or "").strip().lower()
    if v in PRIORITY_VALUES:
        return v  # type: ignore[return-value]
    return default


def _lines(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    if isinstance(value, str):
        return [p.strip() for p in value.replace("|", "\n").splitlines() if p.strip()]
    return []


def default_priorities() -> dict[str, Priority]:
    return {
        "schedule": "hard",
        "area": "hard",
        "title_priority": "important",
        "must_have": "important",
        "commute": "nice",
        "salary": "nice",
    }


def empty_criteria() -> dict[str, Any]:
    return {
        "keywords": "",
        "area_id": None,
        "area_name": "",
        "schedule": "",
        "experience_from": None,
        "salary_to": None,
        "period_days": 7,  # HH API period: resumes updated in last N days; align with HH «Неделя»
        "office_address": "",
        "max_commute_min": 60,
        "office_required": "first_3_months",  # first_3_months | always | no
        "title_priority": [],
        "must_have": [],
        "reject": [],
        "priorities": default_priorities(),
        "portrait": {"hard": [], "important": [], "nice": []},
        "recruiter_comment": "",
        "prefill_meta": {
            "prefilled_at": None,
            "sources": [],
            "recruiter_edited": False,
        },
        "max_search": 20,
        "max_evaluate": 10,
        "smart_prefilter": True,
        "soft_rules": {"ignore": [], "focus": [], "extra_stop": []},
        # HH text rules: keywords = OR alternatives (любое из); keywords_and = required (все / И)
        "keywords_and": "",
        "keywords_logic": "any",  # within a single multi-word OR line when no keywords_and expansion
    }


def normalize_criteria(raw: Any) -> dict[str, Any]:
    base = empty_criteria()
    if not isinstance(raw, dict):
        return base
    data = deepcopy(base)
    data["keywords"] = str(raw.get("keywords") or "").strip()
    area_id = raw.get("area_id")
    try:
        data["area_id"] = int(area_id) if area_id not in (None, "") else None
    except (TypeError, ValueError):
        data["area_id"] = None
    data["area_name"] = str(raw.get("area_name") or "").strip()
    data["schedule"] = str(raw.get("schedule") or "").strip()
    exp = raw.get("experience_from")
    try:
        data["experience_from"] = int(exp) if exp not in (None, "") else None
    except (TypeError, ValueError):
        data["experience_from"] = None
    sal = raw.get("salary_to")
    try:
        data["salary_to"] = int(sal) if sal not in (None, "") else None
    except (TypeError, ValueError):
        data["salary_to"] = None
    if "period_days" in raw:
        period = raw.get("period_days")
        try:
            data["period_days"] = int(period) if period not in (None, "") else None
        except (TypeError, ValueError):
            data["period_days"] = None
        if data["period_days"] is not None:
            data["period_days"] = max(1, min(365, data["period_days"]))
    data["office_address"] = str(raw.get("office_address") or "").strip()
    try:
        data["max_commute_min"] = int(raw.get("max_commute_min") or 60)
    except (TypeError, ValueError):
        data["max_commute_min"] = 60
    office_req = str(raw.get("office_required") or "first_3_months").strip()
    if office_req not in {"first_3_months", "always", "no"}:
        office_req = "first_3_months"
    data["office_required"] = office_req
    data["title_priority"] = _lines(raw.get("title_priority"))
    data["must_have"] = _lines(raw.get("must_have"))
    data["reject"] = _lines(raw.get("reject"))
    pri = dict(default_priorities())
    raw_pri = raw.get("priorities") if isinstance(raw.get("priorities"), dict) else {}
    for key in pri:
        if key in raw_pri:
            pri[key] = _norm_priority(raw_pri[key], pri[key])
    data["priorities"] = pri
    portrait_raw = raw.get("portrait") if isinstance(raw.get("portrait"), dict) else {}
    data["portrait"] = {
        "hard": _lines(portrait_raw.get("hard")),
        "important": _lines(portrait_raw.get("important")),
        "nice": _lines(portrait_raw.get("nice")),
    }
    data["recruiter_comment"] = str(raw.get("recruiter_comment") or "").strip()
    meta_raw = raw.get("prefill_meta") if isinstance(raw.get("prefill_meta"), dict) else {}
    data["prefill_meta"] = {
        "prefilled_at": meta_raw.get("prefilled_at"),
        "sources": list(meta_raw.get("sources") or [])
        if isinstance(meta_raw.get("sources"), list)
        else [],
        "recruiter_edited": bool(meta_raw.get("recruiter_edited")),
        "model": meta_raw.get("model"),
        "skip_prefill": bool(meta_raw.get("skip_prefill")),
    }
    try:
        data["max_search"] = max(1, min(50, int(raw.get("max_search") or 20)))
    except (TypeError, ValueError):
        data["max_search"] = 20
    try:
        data["max_evaluate"] = max(0, min(50, int(raw.get("max_evaluate") or 10)))
    except (TypeError, ValueError):
        data["max_evaluate"] = 10
    if "smart_prefilter" in raw:
        data["smart_prefilter"] = bool(raw.get("smart_prefilter"))
    else:
        data["smart_prefilter"] = True
    soft = raw.get("soft_rules") if isinstance(raw.get("soft_rules"), dict) else {}
    data["soft_rules"] = {
        "ignore": _lines(soft.get("ignore")),
        "focus": _lines(soft.get("focus")),
        "extra_stop": _lines(soft.get("extra_stop")),
    }
    data["keywords_and"] = str(raw.get("keywords_and") or "").strip()
    logic = str(raw.get("keywords_logic") or "any").strip().lower()
    data["keywords_logic"] = logic if logic in ("any", "all") else "any"
    return data


def build_hh_text_queries(criteria: dict[str, Any] | None = None, *, keywords: str = "", keywords_and: str = "", keywords_logic: str = "any") -> list[dict[str, str]]:
    """Build HH /resumes text queries with logic.

    Mirrors HH UI:
    - ``keywords`` lines = alternatives (ИЛИ), like «любое из слов» / several synonym rows
    - ``keywords_and`` = required terms (И), like second block «все слова» (e.g. 1С)

    (A|B|C) AND D  →  queries ``A D``, ``B D``, ``C D`` with text.logic=all
    Only OR, one line with several tokens → one query with text.logic=any (or all)
    """
    from app.services.hh_prefilter import split_queries

    if criteria is not None:
        c = normalize_criteria(criteria)
        keywords = str(c.get("keywords") or "")
        keywords_and = str(c.get("keywords_and") or "")
        keywords_logic = str(c.get("keywords_logic") or "any")

    or_terms = split_queries(keywords)
    and_terms = split_queries(keywords_and)
    if not or_terms and and_terms:
        or_terms = [" ".join(and_terms)]
        and_terms = []
    if not or_terms:
        return []

    logic = keywords_logic if keywords_logic in ("any", "all") else "any"

    # (OR) AND (required) → expand
    if and_terms:
        and_join = " ".join(and_terms)
        return [{"text": f"{term} {and_join}".strip(), "logic": "all"} for term in or_terms]

    # Several OR lines → one HH call with «любое из слов» is closer to the UI
    if len(or_terms) > 1:
        return [{"text": " ".join(or_terms), "logic": "any"}]

    # Single line: respect keywords_logic (any = любое из слов, all = все слова)
    return [{"text": or_terms[0], "logic": logic}]


def build_portrait_from_fields(criteria: dict[str, Any]) -> dict[str, list[str]]:
    """Auto-generate editable portrait lines from structured fields + priorities."""
    c = normalize_criteria(criteria)
    pri = c["priorities"]
    buckets: dict[str, list[str]] = {"hard": [], "important": [], "nice": []}

    def add(field_key: str, line: str) -> None:
        if not line.strip():
            return
        buckets[pri.get(field_key, "important")].append(line.strip())

    if c["schedule"]:
        label = next((o["label"] for o in SCHEDULE_OPTIONS if o["id"] == c["schedule"]), c["schedule"])
        add("schedule", f"Формат/график: {label}")
    if c["office_required"] and c["office_required"] != "no":
        label = (
            "офис первые 3 месяца"
            if c["office_required"] == "first_3_months"
            else "постоянно в офисе"
        )
        # office requirement follows schedule priority by default
        add("schedule", f"Обязателен офис: {label}")
    if c["area_name"] or c["area_id"]:
        name = c["area_name"] or f"area_id={c['area_id']}"
        add("area", f"Город/регион: {name}")
    if c["title_priority"]:
        add("title_priority", "Приоритет в названии/опыте: " + ", ".join(c["title_priority"]))
    if c["must_have"]:
        add("must_have", "Must-have: " + "; ".join(c["must_have"]))
    if c["reject"]:
        # rejects are always hard
        for r in c["reject"]:
            buckets["hard"].append(f"Отсев: {r}")
    if c["office_address"] or c["max_commute_min"]:
        bits = []
        if c["office_address"]:
            bits.append(f"офис: {c['office_address']}")
        if c["max_commute_min"]:
            bits.append(f"дорога до ~{c['max_commute_min']} мин")
        add("commute", "Commute: " + ", ".join(bits))
    if c["salary_to"]:
        add("salary", f"Ориентир зарплаты до {c['salary_to']} (если указана в резюме)")
    if c.get("period_days"):
        add("must_have", f"Резюме обновлено за последние {c['period_days']} дн. (фильтр HH)")
    if c["experience_from"] is not None:
        add("must_have", f"Опыт от {c['experience_from']} лет")
    return buckets


def ensure_portrait(criteria: dict[str, Any], *, rebuild: bool = False) -> dict[str, Any]:
    c = normalize_criteria(criteria)
    has_any = any(c["portrait"][k] for k in ("hard", "important", "nice"))
    if rebuild or not has_any:
        c["portrait"] = build_portrait_from_fields(c)
    return c


def warnings_for(criteria: dict[str, Any]) -> list[dict[str, str]]:
    c = normalize_criteria(criteria)
    out: list[dict[str, str]] = []
    meta = c.get("prefill_meta") or {}
    if meta.get("prefilled_at") and not meta.get("recruiter_edited"):
        sources = ", ".join(meta.get("sources") or []) or "профиль"
        out.append(
            {
                "level": "warning",
                "code": "prefill_unreviewed",
                "text": (
                    f"Критерии заполнены ИИ ({sources}), правок рекрутера ещё не было. "
                    "Проверьте портрет и комментарий перед поиском — иначе снова будет шум."
                ),
            }
        )
    if not c["keywords"]:
        out.append(
            {
                "level": "warning",
                "code": "no_keywords",
                "text": "Нет ключевых запросов — воронка HH будет пустой или слишком широкой.",
            }
        )
    elif len(c["keywords"].split()) < 2 and "\n" not in c["keywords"]:
        out.append(
            {
                "level": "info",
                "code": "weak_keywords",
                "text": "Один короткий запрос — лучше 2–3 близких названия должности (с новой строки).",
            }
        )
    if not c["schedule"] and c["office_required"] != "no":
        out.append(
            {
                "level": "warning",
                "code": "no_schedule",
                "text": "Не задан график HH — remote-only могут попасть в выдачу; ИИ отсечёт только по портрету.",
            }
        )
    if not c["area_id"] and not c["area_name"]:
        out.append(
            {
                "level": "warning",
                "code": "no_area",
                "text": "Город не задан — в выдачу попадут другие регионы; «близко к офису» оценить сложно.",
            }
        )
    if c["office_required"] != "no" and not c["office_address"]:
        out.append(
            {
                "level": "info",
                "code": "no_office_address",
                "text": "Нет адреса офиса — время в пути будет грубым (по городу/району из резюме).",
            }
        )
    if not c["title_priority"]:
        out.append(
            {
                "level": "info",
                "code": "no_title_priority",
                "text": "Нет приоритета названий — сильный «похожий» профиль может обогнать точное совпадение должности.",
            }
        )
    if not c["must_have"] and not c["portrait"]["hard"] and not c["portrait"]["important"]:
        out.append(
            {
                "level": "info",
                "code": "thin_portrait",
                "text": "Портрет почти пустой — оценка будет общей, больше «не тех» кандидатов.",
            }
        )
    if not c.get("period_days"):
        out.append(
            {
                "level": "info",
                "code": "no_period",
                "text": "Нет фильтра свежести — в выдачу попадут и давно не обновлявшиеся резюме.",
            }
        )
    if not c.get("recruiter_comment"):
        out.append(
            {
                "level": "info",
                "code": "no_recruiter_comment",
                "text": "Нет комментария рекрутера — ИИ будет опираться только на портрет и профиль.",
            }
        )
    return out


def criteria_from_vacancy_documents(documents: dict | None, *, title: str = "") -> dict[str, Any]:
    docs = documents or {}
    stored = docs.get(DOC_KEY)
    c = normalize_criteria(stored if isinstance(stored, dict) else {})
    if not c["keywords"]:
        c["keywords"] = extract_keywords(docs)
    if not c["title_priority"] and title:
        # seed one alias from vacancy title
        t = title.strip()
        if t:
            c["title_priority"] = [t]
    return ensure_portrait(c)


def save_criteria_to_documents(documents: dict | None, criteria: dict[str, Any]) -> dict:
    docs = dict(documents or {})
    docs[DOC_KEY] = normalize_criteria(criteria)
    return docs


def portrait_text_for_ai(criteria: dict[str, Any]) -> str:
    c = ensure_portrait(normalize_criteria(criteria))
    parts: list[str] = []
    comment = str(c.get("recruiter_comment") or "").strip()
    if comment:
        parts.extend(
            [
                "КОММЕНТАРИЙ РЕКРУТЕРА (приоритет №1 — руководствуйся им в первую очередь):",
                comment,
                "",
            ]
        )
    parts.extend(
        [
            "ПРАВИЛА ОТБОРА (приоритеты):",
            "• Жёстко — нет совпадения → отсев или rating ≤ 1.",
            "• Важно — нет → сильно понизить rating, но можно оставить в shortlist.",
            "• Желательно — при конфликте «закрывать глаза» в первую очередь.",
            "• Учитывай сферу (industry), уровень должности (не overqualified) и зарплатные ожидания vs вилка.",
            "",
            "ЖЁСТКО:",
        ]
    )
    hard = c["portrait"]["hard"] or ["(не задано)"]
    important = c["portrait"]["important"] or ["(не задано)"]
    nice = c["portrait"]["nice"] or ["(не задано)"]
    parts.extend(f"- {x}" for x in hard)
    parts.append("")
    parts.append("ВАЖНО:")
    parts.extend(f"- {x}" for x in important)
    parts.append("")
    parts.append("ЖЕЛАТЕЛЬНО:")
    parts.extend(f"- {x}" for x in nice)
    if c["keywords"]:
        parts.append("")
        parts.append(f"Ключевые запросы поиска: {c['keywords']}")
    if c.get("salary_to"):
        parts.append(f"Ориентир верхней вилки ЗП: {c['salary_to']}")
    soft = c.get("soft_rules") if isinstance(c.get("soft_rules"), dict) else {}
    ignore = soft.get("ignore") or []
    focus = soft.get("focus") or []
    stop = soft.get("extra_stop") or []
    if ignore or focus or stop:
        parts.append("")
        parts.append("SOFT_RULES ИЗ ПЛАНА ПОИСКА:")
        if ignore:
            parts.append("Не снижать оценку (правка рекрутера):")
            parts.extend(f"- {x}" for x in ignore)
        if focus:
            parts.append("Обратить внимание:")
            parts.extend(f"- {x}" for x in focus)
        if stop:
            parts.append("Доп. стоп-факторы скринера:")
            parts.extend(f"- {x}" for x in stop)
    return "\n".join(parts)


def hh_search_params(criteria: dict[str, Any]) -> dict[str, Any]:
    """Params for HH GET /resumes (hard funnel only).

    Intentionally omit ``schedule``: HH UI searches usually don't lock schedule,
    and fullDay excludes strong hybrid/remote-open candidates in the right city.
    Work format stays a soft rule for ИИ.
    """
    c = normalize_criteria(criteria)
    params: dict[str, Any] = {}
    if c["area_id"] is not None:
        params["area"] = c["area_id"]
    if c["salary_to"]:
        params["salary_to"] = c["salary_to"]
    if c.get("period_days"):
        params["period"] = int(c["period_days"])
    return params


def describe_hh_query_plan(criteria: dict[str, Any]) -> str:
    """Human-readable explanation of OR/AND text plan for UI / debrief."""
    c = normalize_criteria(criteria)
    queries = build_hh_text_queries(c)
    or_lines = [q.strip() for q in (c.get("keywords") or "").splitlines() if q.strip()]
    and_lines = [q.strip() for q in (c.get("keywords_and") or "").splitlines() if q.strip()]
    bits = []
    if or_lines:
        bits.append("ИЛИ (синонимы): " + " · ".join(or_lines))
    if and_lines:
        bits.append("И (обязательно): " + " · ".join(and_lines))
    if queries:
        bits.append(
            "API: "
            + "; ".join(f"«{q['text']}» [{q['logic']}]" for q in queries[:6])
        )
    return " | ".join(bits) if bits else ""
