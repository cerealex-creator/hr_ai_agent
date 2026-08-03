"""ARQ task functions. Update jobs table for UI progress."""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services import jobs as job_svc


async def demo_progress(ctx, job_id: str) -> dict:
    """Safe demo: steps with progress, no side effects on Streamlit data."""
    jid = uuid.UUID(job_id)
    db = SessionLocal()
    try:
        job_svc.update_job(db, jid, status="running", progress_pct=0, progress_label="Старт")
        steps = [
            (20, "Подготовка"),
            (40, "Обработка"),
            (70, "Проверка"),
            (100, "Готово"),
        ]
        for pct, label in steps:
            if job_svc.is_cancelled(db, jid):
                job_svc.update_job(db, jid, progress_label="Отменено")
                return {"ok": False, "cancelled": True}
            await asyncio.sleep(1.2)
            job_svc.update_job(db, jid, progress_pct=pct, progress_label=label)
        job_svc.update_job(
            db,
            jid,
            status="completed",
            progress_pct=100,
            progress_label="Завершено",
            result_ref="demo:ok",
        )
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001 — surface to job row
        job_svc.update_job(
            db,
            jid,
            status="failed",
            progress_label="Ошибка",
            error=str(exc),
        )
        raise
    finally:
        db.close()


async def import_legacy(ctx, job_id: str) -> dict:
    """Re-import snapshot data/ → PostgreSQL (read-only on files)."""
    jid = uuid.UUID(job_id)
    db = SessionLocal()
    try:
        job_svc.update_job(
            db, jid, status="running", progress_pct=5, progress_label="Чтение snapshot"
        )
        if job_svc.is_cancelled(db, jid):
            return {"ok": False, "cancelled": True}

        settings = get_settings()
        data_dir = Path(settings.legacy_data_dir)
        # Allow override from job payload
        job = job_svc.get_job(db, jid)
        if job and (job.payload or {}).get("data_dir"):
            data_dir = Path(str(job.payload["data_dir"]))

        job_svc.update_job(db, jid, progress_pct=25, progress_label="Импорт в PostgreSQL")
        await asyncio.sleep(0.1)

        # Run sync importer off the event loop
        def _run():
            from app.scripts.import_json import run_import

            return run_import(data_dir.resolve(), replace=True)

        stats = await asyncio.to_thread(_run)

        if job_svc.is_cancelled(db, jid):
            job_svc.update_job(db, jid, progress_label="Отменено после импорта")
            return {"ok": False, "cancelled": True, "stats": stats}

        job_svc.update_job(
            db,
            jid,
            status="completed",
            progress_pct=100,
            progress_label="Импорт завершён",
            result_ref="import:ok",
            payload_patch={"stats": stats},
        )
        return {"ok": True, "stats": stats}
    except Exception as exc:  # noqa: BLE001
        job_svc.update_job(
            db,
            jid,
            status="failed",
            progress_label="Ошибка импорта",
            error=str(exc),
        )
        raise
    finally:
        db.close()


async def transcribe_media(ctx, job_id: str) -> dict:
    """Download media → ffmpeg PCM → Yandex SpeechKit. Result in job.payload."""
    jid = uuid.UUID(job_id)
    db = SessionLocal()
    try:
        job = job_svc.get_job(db, jid)
        if not job:
            raise RuntimeError("Job not found")
        source_url = str((job.payload or {}).get("source_url") or "").strip()
        if not source_url:
            raise RuntimeError("В payload нужен source_url (ссылка на видео/аудио)")

        job_svc.update_job(
            db, jid, status="running", progress_pct=2, progress_label="Старт расшифровки"
        )
        if job_svc.is_cancelled(db, jid):
            return {"ok": False, "cancelled": True}

        settings = get_settings()

        def on_progress(pct: int, label: str) -> None:
            # Refresh cancel from DB each tick
            if job_svc.is_cancelled(db, jid):
                return
            job_svc.update_job(db, jid, progress_pct=pct, progress_label=label)

        def should_cancel() -> bool:
            return job_svc.is_cancelled(db, jid)

        def _run():
            from app.services.transcription import transcribe_from_url

            return transcribe_from_url(
                source_url,
                api_key=settings.yandex_api_key,
                bucket=settings.yandex_bucket_name,
                access_key=settings.yandex_access_key_id,
                secret_key=settings.yandex_secret_access_key,
                ffmpeg_binary=settings.ffmpeg_binary,
                on_progress=on_progress,
                should_cancel=should_cancel,
            )

        result = await asyncio.to_thread(_run)

        if job_svc.is_cancelled(db, jid):
            job_svc.update_job(db, jid, progress_label="Отменено")
            return {"ok": False, "cancelled": True}

        job_svc.update_job(
            db,
            jid,
            status="completed",
            progress_pct=100,
            progress_label=f"Готово · {result.get('chars', 0)} симв.",
            result_ref=f"transcript:{result.get('chars', 0)}",
            payload_patch={
                "transcript": result.get("transcript"),
                "preview": result.get("preview"),
                "chars": result.get("chars"),
            },
        )
        return {"ok": True, "chars": result.get("chars")}
    except Exception as exc:  # noqa: BLE001
        msg = str(exc)
        if msg == "Отменено" or job_svc.is_cancelled(db, jid):
            job_svc.update_job(db, jid, status="cancelled", progress_label="Отменено")
            return {"ok": False, "cancelled": True}
        job_svc.update_job(
            db,
            jid,
            status="failed",
            progress_label="Ошибка расшифровки",
            error=msg,
        )
        raise
    finally:
        db.close()


async def candidate_interview_process(ctx, job_id: str) -> dict:
    """Transcribe candidate interview recording, clean text and run interview eval."""
    jid = uuid.UUID(job_id)
    db = SessionLocal()
    try:
        from sqlalchemy.orm.attributes import flag_modified

        from app.db import models
        from app.services.candidate_interview_eval import evaluate_candidate_interview
        from app.services.transcription import cleanup_transcript_text, transcribe_from_url

        job = job_svc.get_job(db, jid)
        if not job:
            raise RuntimeError("Job not found")
        payload = dict(job.payload or {})
        candidate_id = str(payload.get("candidate_id") or "").strip()
        if not candidate_id:
            raise RuntimeError("Нужен candidate_id")
        candidate = db.get(models.Candidate, uuid.UUID(candidate_id))
        if not candidate:
            raise RuntimeError("Кандидат не найден")
        source_url = str(payload.get("source_url") or (candidate.payload or {}).get("video_link") or "").strip()
        if not source_url:
            raise RuntimeError("Добавьте ссылку на запись собеседования")

        job_svc.update_job(
            db, jid, status="running", progress_pct=2, progress_label="Старт обработки собеседования"
        )
        if job_svc.is_cancelled(db, jid):
            return {"ok": False, "cancelled": True}

        settings = get_settings()

        def on_progress(pct: int, label: str) -> None:
            if job_svc.is_cancelled(db, jid):
                return
            job_svc.update_job(db, jid, progress_pct=pct, progress_label=label)

        def should_cancel() -> bool:
            return job_svc.is_cancelled(db, jid)

        def _run():
            result = transcribe_from_url(
                source_url,
                api_key=settings.yandex_api_key,
                bucket=settings.yandex_bucket_name,
                access_key=settings.yandex_access_key_id,
                secret_key=settings.yandex_secret_access_key,
                ffmpeg_binary=settings.ffmpeg_binary,
                on_progress=on_progress,
                should_cancel=should_cancel,
            )
            cleaned = cleanup_transcript_text(result.get("transcript") or "", settings)
            return result, cleaned

        result, cleaned = await asyncio.to_thread(_run)
        if job_svc.is_cancelled(db, jid):
            job_svc.update_job(db, jid, progress_label="Отменено")
            return {"ok": False, "cancelled": True}

        cand_payload = dict(candidate.payload or {})
        cand_payload["transcript"] = cleaned
        cand_payload["video_link"] = source_url
        candidate.payload = cand_payload
        flag_modified(candidate, "payload")
        db.add(candidate)
        db.commit()
        db.refresh(candidate)

        job_svc.update_job(db, jid, progress_pct=92, progress_label="Оценка кандидата по собеседованию")
        ev = evaluate_candidate_interview(db, candidate, settings=settings)
        db.refresh(candidate)

        job_svc.update_job(
            db,
            jid,
            status="completed",
            progress_pct=100,
            progress_label=f"Готово · оценка {ev.get('ai_score', '—')}/4",
            result_ref=f"candidate_interview:{candidate.id}",
            payload_patch={
                "candidate_id": str(candidate.id),
                "candidate_name": candidate.name,
                "source_url": source_url,
                "transcript": cleaned,
                "preview": cleaned[:280] + ("…" if len(cleaned) > 280 else ""),
                "chars": len(cleaned),
                "ai_score": ev.get("ai_score"),
            },
        )
        return {"ok": True, "candidate_id": str(candidate.id), "ai_score": ev.get("ai_score")}
    except Exception as exc:  # noqa: BLE001
        msg = str(exc)
        if msg == "Отменено" or job_svc.is_cancelled(db, jid):
            job_svc.update_job(db, jid, status="cancelled", progress_label="Отменено")
            return {"ok": False, "cancelled": True}
        job_svc.update_job(
            db,
            jid,
            status="failed",
            progress_label="Ошибка обработки собеседования",
            error=msg,
        )
        raise
    finally:
        db.close()


async def hh_cold_search(ctx, job_id: str) -> dict:
    """HH resume search (no contacts) + AI rank for a vacancy."""
    jid = uuid.UUID(job_id)
    db = SessionLocal()
    try:
        from app.db import models
        from app.services.hh_client import HhClient, search_resume_items
        from app.services.hh_resume_text import resume_card_summary, resume_to_text
        from app.services.hh_search_criteria import (
            criteria_from_vacancy_documents,
            ensure_portrait,
            hh_search_params,
            normalize_criteria,
            portrait_text_for_ai,
        )
        from app.services.resume_eval import evaluate_resume_text
        from app.services.vacancy_docs import extract_profile_text

        job = job_svc.get_job(db, jid)
        if not job:
            raise RuntimeError("Job not found")
        payload = dict(job.payload or {})
        vacancy_id = job.vacancy_id or payload.get("vacancy_id")
        if vacancy_id is None:
            raise RuntimeError("Нужен vacancy_id")
        vacancy_id = int(vacancy_id)

        vacancy = db.get(models.Vacancy, vacancy_id)
        if not vacancy:
            raise RuntimeError(f"Вакансия {vacancy_id} не найдена")

        criteria = normalize_criteria(payload.get("criteria") or {})
        if not criteria.get("keywords"):
            criteria = criteria_from_vacancy_documents(vacancy.documents, title=vacancy.title)
        criteria = ensure_portrait(criteria)
        keywords = str(criteria.get("keywords") or "").strip()
        if not keywords:
            raise RuntimeError(
                "Нет ключевых слов: укажите в критериях поиска вакансии"
            )

        max_search = int(criteria.get("max_search") or payload.get("max_search") or 20)
        max_evaluate = int(criteria.get("max_evaluate") or payload.get("max_evaluate") or 10)
        max_search = max(1, min(50, max_search))
        max_evaluate = max(0, min(max_search, max_evaluate))
        funnel = hh_search_params(criteria)
        selection_rules = portrait_text_for_ai(criteria)

        settings = get_settings()
        job_svc.update_job(
            db,
            jid,
            status="running",
            progress_pct=5,
            progress_label="Поиск на HH…",
            payload_patch={
                "keywords": keywords,
                "criteria": criteria,
                "vacancy_title": vacancy.title,
            },
        )
        if job_svc.is_cancelled(db, jid):
            return {"ok": False, "cancelled": True}

        def _search():
            client = HhClient(settings)
            return search_resume_items(
                client,
                keywords,
                max_items=max_search,
                area=funnel.get("area"),
                schedule=funnel.get("schedule"),
                salary_to=funnel.get("salary_to"),
                period=funnel.get("period"),
                prioritized=True,
            )

        hits = await asyncio.to_thread(_search)

        from app.services.hh_prefilter import select_for_evaluation
        from app.services.hh_seen import excluded_map, mark_ai_low_scores, reason_label

        excluded = excluded_map(db, vacancy_id)
        fresh_hits: list[dict] = []
        seen_hits: list[dict] = []
        for hit in hits:
            rid = str(hit.get("id") or "")
            if rid and rid in excluded:
                tagged = dict(hit)
                info = excluded[rid]
                tagged["_skipped_seen"] = True
                tagged["_seen_reason"] = info.get("reason")
                tagged["_seen_label"] = info.get("label") or reason_label(info.get("reason"))
                seen_hits.append(tagged)
            else:
                fresh_hits.append(hit)

        to_eval, not_eval, pre_stats = select_for_evaluation(
            fresh_hits,
            max_evaluate=max_evaluate,
            criteria=criteria,
            vacancy_title=vacancy.title,
            enabled=bool(criteria.get("smart_prefilter", True)),
        )
        pre_stats = dict(pre_stats)
        pre_stats["seen_skip"] = len(seen_hits)

        job_svc.update_job(
            db,
            jid,
            progress_pct=25,
            progress_label=(
                f"Найдено {len(hits)}"
                + (f", уже смотрели {len(seen_hits)}" if seen_hits else "")
                + (f", отсев {pre_stats.get('hard_skip', 0)}" if pre_stats.get("hard_skip") else "")
                + f". Оценка {len(to_eval)}…"
            ),
            payload_patch={"found": len(hits), "prefilter": pre_stats},
        )

        profile = extract_profile_text(vacancy.documents)
        results: list[dict] = []

        client = HhClient(settings)
        for idx, hit in enumerate(to_eval):
            if job_svc.is_cancelled(db, jid):
                job_svc.update_job(db, jid, progress_label="Отменено")
                return {"ok": False, "cancelled": True, "results": results}
            rid = str(hit.get("id") or "")
            pct = 25 + int(70 * (idx + 1) / max(len(to_eval), 1))
            job_svc.update_job(
                db,
                jid,
                progress_pct=min(95, pct),
                progress_label=f"Оценка {idx + 1}/{len(to_eval)}…",
            )

            card = resume_card_summary(hit)
            entry: dict = {
                **card,
                "ai_score": None,
                "ai_preview": "",
                "ai_comment_sections": {},
                "title_fit": None,
                "office_fit": None,
                "commute_ok": None,
                "error": None,
                "contacts_opened": False,
                "source_query": hit.get("_source_query"),
                "prefilter_bucket": hit.get("_prefilter_bucket"),
                "prefilter_reason": hit.get("_prefilter_reason") or "",
            }
            try:

                def _fetch_and_eval(resume_id: str = rid):
                    full = client.get_resume(resume_id)
                    text = resume_to_text(full)
                    if not text:
                        raise RuntimeError("Пустое резюме без контактов — мало данных")
                    ev = evaluate_resume_text(
                        text,
                        profile,
                        vacancy.title,
                        settings,
                        selection_rules=selection_rules,
                    )
                    summary = resume_card_summary(full)
                    return ev, summary

                ev, summary = await asyncio.to_thread(_fetch_and_eval)
                entry.update(summary)
                entry["ai_score"] = ev.get("ai_score")
                entry["ai_preview"] = ev.get("ai_preview")
                entry["ai_comment_sections"] = ev.get("ai_comment_sections") or {}
                entry["ai_strengths"] = ev.get("ai_strengths") or []
                entry["ai_weaknesses"] = ev.get("ai_weaknesses") or []
                entry["title_fit"] = ev.get("title_fit")
                entry["office_fit"] = ev.get("office_fit")
                entry["commute_ok"] = ev.get("commute_ok")
            except Exception as exc:  # noqa: BLE001
                entry["error"] = str(exc)
            results.append(entry)

        for hit in not_eval:
            card = resume_card_summary(hit)
            hard = hit.get("_prefilter_bucket") == "hard" or hit.get("_skipped_prefilter")
            results.append(
                {
                    **card,
                    "ai_score": None,
                    "ai_preview": "",
                    "ai_comment_sections": {},
                    "title_fit": None,
                    "office_fit": None,
                    "commute_ok": None,
                    "error": None,
                    "contacts_opened": False,
                    "skipped_eval": True,
                    "skipped_prefilter": bool(hard),
                    "skipped_seen": False,
                    "source_query": hit.get("_source_query"),
                    "prefilter_bucket": hit.get("_prefilter_bucket"),
                    "prefilter_reason": hit.get("_prefilter_reason") or (
                        "отсеян до оценки" if hard else "лимит оценки"
                    ),
                }
            )

        for hit in seen_hits:
            card = resume_card_summary(hit)
            results.append(
                {
                    **card,
                    "ai_score": None,
                    "ai_preview": "",
                    "ai_comment_sections": {},
                    "title_fit": None,
                    "office_fit": None,
                    "commute_ok": None,
                    "error": None,
                    "contacts_opened": False,
                    "skipped_eval": True,
                    "skipped_prefilter": False,
                    "skipped_seen": True,
                    "seen_reason": hit.get("_seen_reason"),
                    "seen_label": hit.get("_seen_label") or "уже смотрели",
                    "source_query": hit.get("_source_query"),
                    "prefilter_reason": hit.get("_seen_label") or "уже смотрели",
                }
            )

        fit_rank = {"yes": 3, "partial": 2, "unknown": 1, "no": 0, None: -1}

        def _sort_key(r: dict):
            return (
                r.get("ai_score") is not None,
                not r.get("skipped_seen"),
                not r.get("skipped_prefilter"),
                fit_rank.get(r.get("office_fit"), -1),
                fit_rank.get(r.get("title_fit"), -1),
                r.get("ai_score") if r.get("ai_score") is not None else -1,
            )

        results.sort(key=_sort_key, reverse=True)

        marked = mark_ai_low_scores(db, vacancy_id, results)

        job_svc.update_job(
            db,
            jid,
            status="completed",
            progress_pct=100,
            progress_label=(
                f"Готово · оценено {len(to_eval)} из {len(hits)}"
                + (f" · отсев {pre_stats.get('hard_skip', 0)}" if pre_stats.get("hard_skip") else "")
                + (f" · уже смотрели {len(seen_hits)}" if seen_hits else "")
                + (f" · добор {pre_stats.get('soft_backfill', 0)}" if pre_stats.get("soft_backfill") else "")
                + (f" · в бан AI≤1: {marked}" if marked else "")
            ),
            result_ref=f"hh_search:{len(results)}",
            payload_patch={
                "results": results,
                "found": len(hits),
                "evaluated": len(to_eval),
                "prefilter": pre_stats,
                "seen_marked_low": marked,
                "keywords": keywords,
                "criteria": criteria,
            },
        )
        return {
            "ok": True,
            "found": len(hits),
            "evaluated": len(to_eval),
            "prefilter": pre_stats,
            "seen_marked_low": marked,
        }
    except Exception as exc:  # noqa: BLE001
        msg = str(exc)
        if job_svc.is_cancelled(db, jid):
            job_svc.update_job(db, jid, status="cancelled", progress_label="Отменено")
            return {"ok": False, "cancelled": True}
        job_svc.update_job(
            db,
            jid,
            status="failed",
            progress_label="Ошибка HH-поиска",
            error=msg,
        )
        raise
    finally:
        db.close()


async def yandex_disk_sync(ctx, job_id: str) -> dict:
    """Attach resume/video/task links from vacancy public Yandex Disk folder."""
    jid = uuid.UUID(job_id)
    db = SessionLocal()
    try:
        job = job_svc.get_job(db, jid)
        if not job:
            raise RuntimeError("Job not found")
        vacancy_id = job.vacancy_id or (job.payload or {}).get("vacancy_id")
        if vacancy_id is None:
            raise RuntimeError("Нужен vacancy_id")

        job_svc.update_job(
            db, jid, status="running", progress_pct=5, progress_label="Синхронизация Диска"
        )
        if job_svc.is_cancelled(db, jid):
            return {"ok": False, "cancelled": True}

        from app.db import models

        def _run():
            local = SessionLocal()
            try:
                from app.services.yandex_disk_sync import sync_vacancy_yandex_disk

                vac = local.get(models.Vacancy, int(vacancy_id))
                if not vac:
                    raise RuntimeError("Vacancy not found")
                return sync_vacancy_yandex_disk(local, vac).as_dict()
            finally:
                local.close()

        result = await asyncio.to_thread(_run)

        if job_svc.is_cancelled(db, jid):
            job_svc.update_job(db, jid, progress_label="Отменено")
            return {"ok": False, "cancelled": True}

        job_svc.update_job(
            db,
            jid,
            status="completed",
            progress_pct=100,
            progress_label=(
                f"Готово · +{result.get('created', 0)} / обн. {result.get('updated', 0)}"
            ),
            result_ref="yandex_disk:ok",
            payload_patch={"sync": result},
        )
        return {"ok": True, **result}
    except Exception as exc:  # noqa: BLE001
        if job_svc.is_cancelled(db, jid):
            job_svc.update_job(db, jid, status="cancelled", progress_label="Отменено")
            return {"ok": False, "cancelled": True}
        job_svc.update_job(
            db,
            jid,
            status="failed",
            progress_label="Ошибка синхронизации Диска",
            error=str(exc),
        )
        raise
    finally:
        db.close()
