"""Поиск кандидатов по ФИО, контактам и тексту резюме."""

from __future__ import annotations

from dataclasses import dataclass

from models import format_stage_title_label


@dataclass
class CandidateSearchHit:
    candidate: dict
    vacancy: dict
    score: int
    match_in: str

    @property
    def candidate_id(self):
        return self.candidate.get("id") or ""

    @property
    def vacancy_id(self):
        return self.vacancy.get("id")


def _searchable_text(candidate: dict) -> str:
    parts = [
        candidate.get("name") or "",
        candidate.get("phone") or "",
        candidate.get("city") or "",
        candidate.get("metro") or "",
        candidate.get("age_location") or "",
        candidate.get("resume_text") or "",
        candidate.get("hr_comment") or "",
    ]
    return " ".join(p for p in parts if p).casefold()


def _match_score(query_fold: str, words: list[str], candidate: dict) -> tuple[int, str]:
    name = (candidate.get("name") or "").casefold()
    phone = (candidate.get("phone") or "").casefold()
    resume = (candidate.get("resume_text") or "").casefold()
    haystack = _searchable_text(candidate)

    if not haystack:
        return 0, ""

    if query_fold in name:
        return 100, "ФИО"
    if words and all(w in name for w in words):
        return 90, "ФИО"
    if query_fold in phone:
        return 80, "телефон"
    if query_fold in resume:
        return 70, "резюме"
    if query_fold in haystack:
        return 60, "карточка"
    if words and all(w in haystack for w in words):
        return 50, "карточка"
    return 0, ""


def search_candidates(vacancies, query: str, *, include_test: bool = False, limit: int = 40):
    """Ищет по всем вакансиям (активным и архивным)."""
    query = (query or "").strip()
    if len(query) < 2:
        return []

    query_fold = query.casefold()
    words = [w for w in query_fold.split() if len(w) >= 2]
    hits: list[CandidateSearchHit] = []

    for vacancy in vacancies:
        if not include_test and vacancy.get("is_test"):
            continue
        for cand in vacancy.get("candidates", []):
            score, match_in = _match_score(query_fold, words, cand)
            if score <= 0:
                continue
            hits.append(CandidateSearchHit(candidate=cand, vacancy=vacancy, score=score, match_in=match_in))

    hits.sort(
        key=lambda h: (
            -h.score,
            h.candidate.get("name") or "",
            h.vacancy.get("title") or "",
        )
    )
    return hits[:limit]


def format_hit_summary(hit: CandidateSearchHit) -> str:
    stage = format_stage_title_label(hit.candidate.get("hr_stage", "resume_screening"))
    if hit.vacancy.get("is_test"):
        vac_status = "тестовая вакансия"
    elif hit.vacancy.get("active", True):
        vac_status = "в работе"
    else:
        vac_status = "архив"
    return f"{hit.candidate.get('name') or 'Без имени'} · {stage} · {hit.vacancy.get('title', '—')} ({vac_status})"


def resume_snippet(candidate: dict, query: str, *, max_len: int = 220) -> str:
    text = (candidate.get("resume_text") or "").strip()
    if not text:
        return ""
    q = query.strip().casefold()
    if not q:
        return text[:max_len] + ("…" if len(text) > max_len else "")
    pos = text.casefold().find(q)
    if pos < 0:
        words = [w for w in q.split() if len(w) >= 2]
        for w in words:
            pos = text.casefold().find(w)
            if pos >= 0:
                break
    if pos < 0:
        return text[:max_len] + ("…" if len(text) > max_len else "")
    start = max(0, pos - 60)
    end = min(len(text), pos + max_len)
    snippet = text[start:end]
    if start > 0:
        snippet = "…" + snippet
    if end < len(text):
        snippet += "…"
    return snippet
