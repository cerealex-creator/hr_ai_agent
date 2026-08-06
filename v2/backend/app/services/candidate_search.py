"""Global candidate text search (name / phone / resume / card)."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models
from app.services.candidate_query import last_contact_map, serialize_list_item, vacancy_meta_maps


@dataclass
class CandidateSearchHit:
    candidate: models.Candidate
    vacancy: models.Vacancy
    score: int
    match_in: str


def _searchable_text(candidate: models.Candidate) -> str:
    p = candidate.payload or {}
    parts = [
        candidate.name or "",
        str(p.get("phone") or ""),
        str(p.get("city") or ""),
        str(p.get("metro") or ""),
        str(p.get("age_location") or ""),
        str(p.get("resume_text") or ""),
        str(p.get("hr_comment") or ""),
    ]
    return " ".join(x for x in parts if x).casefold()


def _match_score(query_fold: str, words: list[str], candidate: models.Candidate) -> tuple[int, str]:
    p = candidate.payload or {}
    name = (candidate.name or "").casefold()
    phone = str(p.get("phone") or "").casefold()
    resume = str(p.get("resume_text") or "").casefold()
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


def search_candidates(
    db: Session,
    query: str,
    *,
    include_test: bool = False,
    limit: int = 40,
    organization_id=None,
) -> list[dict]:
    query = (query or "").strip()
    if len(query) < 2:
        return []
    query_fold = query.casefold()
    words = [w for w in query_fold.split() if len(w) >= 2]
    vq = select(models.Vacancy)
    if organization_id is not None:
        from app.services.tenancy import org_client_ids

        cids = org_client_ids(db, organization_id)
        if not cids:
            return []
        vq = vq.where(models.Vacancy.client_id.in_(cids))
    vacancies = {v.id: v for v in db.scalars(vq).all()}
    hits: list[CandidateSearchHit] = []
    cq = select(models.Candidate)
    if vacancies:
        cq = cq.where(models.Candidate.vacancy_id.in_(list(vacancies.keys())))
    else:
        return []
    for cand in db.scalars(cq).all():
        vac = vacancies.get(cand.vacancy_id)
        if not vac:
            continue
        if not include_test and bool((vac.payload or {}).get("is_test")):
            continue
        score, match_in = _match_score(query_fold, words, cand)
        if score <= 0:
            continue
        hits.append(CandidateSearchHit(candidate=cand, vacancy=vac, score=score, match_in=match_in))
    hits.sort(key=lambda h: (-h.score, (h.candidate.name or "").casefold()))
    hits = hits[: max(1, min(limit, 100))]
    titles, client_names = vacancy_meta_maps(db, list({h.vacancy.id: h.vacancy for h in hits}.values()))
    posts = last_contact_map(db, [h.candidate.id for h in hits])
    out = []
    for h in hits:
        item = serialize_list_item(
            h.candidate,
            vacancy_title=titles.get(h.candidate.vacancy_id),
            client_name=client_names.get(h.candidate.vacancy_id),
            last_contact_at=posts.get(h.candidate.id),
        )
        item["match_in"] = h.match_in
        item["score"] = h.score
        out.append(item)
    return out
