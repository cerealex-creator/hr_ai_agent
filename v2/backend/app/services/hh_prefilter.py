"""Cheap pre-filter of HH search hits before full resume fetch + AI eval."""

from __future__ import annotations

import re
from typing import Any

# Titles that usually mean overqualified for specialist / executor roles
SENIORITY_PATTERNS = re.compile(
    r"("
    r"руководител\w*\s+направлен|"
    r"руководитель\s+отдела|"
    r"руководитель\s+группы|"
    r"начальник\s+отдела|"
    r"директор|"
    r"head\s+of|"
    r"\bceo\b|\bcoo\b|\bcto\b|\bcmo\b|"
    r"chief\s+\w+|"
    r"vice\s+president|\bvp\b|"
    r"управляющий\s+директор|"
    r"генеральный\s+директор"
    r")",
    re.IGNORECASE,
)

SENIORITY_VACANCY = re.compile(
    r"руководител|директор|head\s+of|chief\s+|начальник",
    re.IGNORECASE,
)


def split_queries(keywords: str) -> list[str]:
    parts = [q.strip() for q in (keywords or "").replace("|", "\n").splitlines() if q.strip()]
    return parts or ([keywords.strip()] if (keywords or "").strip() else [])


def query_quotas(n_queries: int, max_items: int) -> list[int]:
    """Higher weight for earlier keyword lines. Sum == max_items."""
    max_items = max(1, max_items)
    if n_queries <= 1:
        return [max_items]
    if n_queries == 2:
        first = max(1, int(round(max_items * 0.6)))
        first = min(first, max_items - 1)
        return [first, max_items - first]
    # 50% / 30% / rest share 20%
    first = max(1, int(round(max_items * 0.5)))
    second = max(1, int(round(max_items * 0.3)))
    if first + second >= max_items:
        first = max(1, max_items // 2)
        second = max(1, max_items - first - (n_queries - 2))
        second = max(0, second)
    remaining = max_items - first - second
    rest_n = n_queries - 2
    rest = [0] * rest_n
    if remaining > 0 and rest_n > 0:
        base = remaining // rest_n
        extra = remaining % rest_n
        for i in range(rest_n):
            rest[i] = base + (1 if i < extra else 0)
    quotas = [first, second, *rest]
    # fix sum drift
    diff = max_items - sum(quotas)
    if diff and quotas:
        quotas[0] = max(1, quotas[0] + diff)
    return quotas


def _norm_phrases(values: list[str] | None) -> list[str]:
    out: list[str] = []
    for v in values or []:
        s = str(v).strip().lower()
        if len(s) >= 2:
            out.append(s)
    return out


def _title_hits_phrase(title: str, phrases: list[str]) -> str | None:
    t = (title or "").lower()
    for p in phrases:
        if p in t:
            return p
    return None


def _hit_area_id(hit: dict[str, Any]) -> int | None:
    area = hit.get("area") or {}
    if not isinstance(area, dict):
        return None
    try:
        return int(area.get("id")) if area.get("id") is not None else None
    except (TypeError, ValueError):
        return None


def _hit_area_name(hit: dict[str, Any]) -> str:
    area = hit.get("area") or {}
    if isinstance(area, dict):
        return str(area.get("name") or "").strip()
    return ""


def area_mismatch_reason(
    hit: dict[str, Any],
    *,
    area_id: int | None,
    area_name: str = "",
) -> str | None:
    """If vacancy locks a city, reject other cities before AI eval."""
    if area_id is None and not (area_name or "").strip():
        return None
    hid = _hit_area_id(hit)
    hname = _hit_area_name(hit)
    if area_id is not None and hid is not None and hid != int(area_id):
        label = hname or f"area_id={hid}"
        return f"другой город: {label}"
    want = (area_name or "").strip().lower()
    if want and hname:
        hn = hname.lower()
        if want not in hn and hn not in want:
            # allow short aliases
            tokens = [t for t in want.replace("-", " ").split() if len(t) >= 4]
            if tokens and not any(t in hn for t in tokens):
                return f"другой город: {hname}"
    return None


def classify_hit(
    hit: dict[str, Any],
    *,
    title_priority: list[str],
    reject: list[str],
    keyword_phrases: list[str],
    vacancy_title: str = "",
    area_id: int | None = None,
    area_name: str = "",
) -> tuple[str, str]:
    """
    Returns (bucket, reason):
      hard  — never evaluate
      boost — prefer for eval
      ok    — fine for eval
      soft  — title weak match; use only when backfilling
    """
    geo = area_mismatch_reason(hit, area_id=area_id, area_name=area_name)
    if geo:
        return "hard", geo

    title = str(hit.get("title") or "").strip()
    vac_is_senior = bool(SENIORITY_VACANCY.search(vacancy_title or ""))

    if not vac_is_senior and title and SENIORITY_PATTERNS.search(title):
        return "hard", "уровень: руководящая должность в названии"

    reject_phrases = _norm_phrases(reject)
    hit_reject = _title_hits_phrase(title, reject_phrases)
    if hit_reject:
        return "hard", f"отсев по title: «{hit_reject}»"

    aliases = _norm_phrases(title_priority)
    if aliases and _title_hits_phrase(title, aliases):
        return "boost", "совпадение с приоритетом названий"

    kw = _norm_phrases(keyword_phrases)
    if aliases and not _title_hits_phrase(title, aliases):
        if kw and _title_hits_phrase(title, kw):
            return "ok", "есть пересечение с запросом"
        if aliases:
            return "soft", "название далеко от приоритета"
    return "ok", ""


def select_for_evaluation(
    hits: list[dict[str, Any]],
    *,
    max_evaluate: int,
    criteria: dict[str, Any],
    vacancy_title: str = "",
    enabled: bool = True,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, int]]:
    """
    Pick hits for AI eval. Hard rejects never evaluated.
    Soft (weak title) used only to backfill when boost/ok are not enough.
    Returns (to_eval, not_eval_hits_with_meta, stats).
    """
    max_evaluate = max(0, max_evaluate)
    if max_evaluate == 0:
        return [], list(hits), {"hard_skip": 0, "soft_backfill": 0, "to_eval": 0}

    if not enabled:
        to_eval = hits[:max_evaluate]
        rest = hits[max_evaluate:]
        for h in to_eval:
            h["_prefilter_bucket"] = "ok"
            h["_prefilter_reason"] = "prefilter выключен"
        for h in rest:
            h["_prefilter_bucket"] = "rest"
            h["_prefilter_reason"] = "лимит оценки"
        return to_eval, rest, {"hard_skip": 0, "soft_backfill": 0, "to_eval": len(to_eval)}

    title_priority = list(criteria.get("title_priority") or [])
    reject = list(criteria.get("reject") or [])
    keyword_phrases = split_queries(str(criteria.get("keywords") or ""))
    area_id = criteria.get("area_id")
    try:
        area_id_i = int(area_id) if area_id not in (None, "") else None
    except (TypeError, ValueError):
        area_id_i = None
    area_name = str(criteria.get("area_name") or "").strip()

    boost: list[dict] = []
    ok: list[dict] = []
    soft: list[dict] = []
    hard: list[dict] = []

    # Preserve HH/query order within buckets (hits already ordered by query priority)
    for hit in hits:
        bucket, reason = classify_hit(
            hit,
            title_priority=title_priority,
            reject=reject,
            keyword_phrases=keyword_phrases,
            vacancy_title=vacancy_title,
            area_id=area_id_i,
            area_name=area_name,
        )
        tagged = dict(hit)
        tagged["_prefilter_bucket"] = bucket
        tagged["_prefilter_reason"] = reason
        if bucket == "hard":
            hard.append(tagged)
        elif bucket == "boost":
            boost.append(tagged)
        elif bucket == "soft":
            soft.append(tagged)
        else:
            ok.append(tagged)

    preferred = boost + ok
    to_eval = preferred[:max_evaluate]
    soft_backfill = 0
    if len(to_eval) < max_evaluate:
        need = max_evaluate - len(to_eval)
        extra = soft[:need]
        soft_backfill = len(extra)
        to_eval = to_eval + extra

    taken_ids = {str(h.get("id") or h.get("hh_resume_id") or "") for h in to_eval}
    not_eval: list[dict] = []
    for h in hard:
        h = dict(h)
        h["_skipped_prefilter"] = True
        not_eval.append(h)
    for pool in (preferred[max_evaluate:], soft[soft_backfill:]):
        for h in pool:
            rid = str(h.get("id") or "")
            if rid and rid in taken_ids:
                continue
            h = dict(h)
            h["_skipped_prefilter"] = False
            h["_prefilter_bucket"] = h.get("_prefilter_bucket") or "rest"
            if not h.get("_prefilter_reason"):
                h["_prefilter_reason"] = "лимит оценки"
            not_eval.append(h)

    stats = {
        "hard_skip": len(hard),
        "soft_backfill": soft_backfill,
        "to_eval": len(to_eval),
        "boost": len(boost),
        "ok": len(ok),
        "soft": len(soft),
    }
    return to_eval, not_eval, stats
