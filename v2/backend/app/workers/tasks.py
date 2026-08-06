"""ARQ task functions. Update jobs table for UI progress."""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services import jobs as job_svc
from app.services.log_sanitize import sanitize_for_log


def _safe_err(exc: BaseException, *, max_len: int = 500) -> str:
    return sanitize_for_log(exc, max_len=max_len)


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
            error=_safe_err(exc),
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
            error=_safe_err(exc),
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
            # Own Session — called from to_thread (audit M5)
            if job_svc.is_cancelled_isolated(jid):
                return
            job_svc.update_job_isolated(jid, progress_pct=pct, progress_label=label)

        def should_cancel() -> bool:
            return job_svc.is_cancelled_isolated(jid)

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
        msg = _safe_err(exc)
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
            if job_svc.is_cancelled_isolated(jid):
                return
            job_svc.update_job_isolated(jid, progress_pct=pct, progress_label=label)

        def should_cancel() -> bool:
            return job_svc.is_cancelled_isolated(jid)

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
        msg = _safe_err(exc)
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
        from app.services.hh_client import HhClient, search_resume_items_from_preset
        from app.services.hh_preset import (
            criteria_view_from_preset,
            describe_preset_query,
            ensure_soft_portrait,
            normalize_preset,
            preset_from_vacancy_documents,
            save_preset_to_documents,
        )
        from app.services.hh_resume_text import resume_card_summary, resume_to_text
        from app.services.hh_search_criteria import (
            ensure_portrait,
            portrait_text_for_ai,
        )
        from app.services.resume_eval import evaluate_resume_text
        from app.services.vacancy_docs import extract_profile_text
        from sqlalchemy.orm.attributes import flag_modified

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

        preset = normalize_preset(payload.get("preset") or {})
        texts_ok = any((t.get("text") or "").strip() for t in preset["api"]["texts"])
        if not texts_ok:
            preset = preset_from_vacancy_documents(vacancy.documents, title=vacancy.title)
            # Persist migrated preset so next runs are deterministic
            if (vacancy.documents or {}).get("hh_preset") is None:
                vacancy.documents = save_preset_to_documents(vacancy.documents, preset)
                flag_modified(vacancy, "documents")
                db.add(vacancy)
                db.commit()
                db.refresh(vacancy)
        preset = ensure_soft_portrait(preset)
        criteria = ensure_portrait(criteria_view_from_preset(preset))
        keywords = str(criteria.get("keywords") or "").strip()
        if not keywords:
            raise RuntimeError("Нет ключевых слов в пресете поиска HH")

        max_search = int(preset["run"].get("max_search") or payload.get("max_search") or 40)
        max_evaluate = int(preset["run"].get("max_evaluate") or payload.get("max_evaluate") or 15)
        max_search = max(1, min(50, max_search))
        max_evaluate = max(0, min(max_search, max_evaluate))
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
                "preset": preset,
                "criteria": criteria,
                "vacancy_title": vacancy.title,
                "query_plan": describe_preset_query(preset),
            },
        )
        if job_svc.is_cancelled(db, jid):
            return {"ok": False, "cancelled": True}

        def _search(hh_client: HhClient):
            return search_resume_items_from_preset(
                hh_client,
                preset,
                max_items=max_search,
            )

        client = HhClient(settings)
        hits = await asyncio.to_thread(_search, client)

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
                entry["error"] = _safe_err(exc)
            results.append(entry)
            # Soft rate-limit between HH get_resume + AI evals (audit Q9)
            if idx + 1 < len(to_eval):
                await asyncio.sleep(0.4)

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

        from app.services.hh_search_debrief import build_debrief

        debrief = build_debrief(
            results=results,
            found=len(hits),
            evaluated=len(to_eval),
            criteria=criteria,
            settings=settings,
        )

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
                "debrief": debrief,
            },
        )
        return {
            "ok": True,
            "found": len(hits),
            "evaluated": len(to_eval),
            "prefilter": pre_stats,
            "seen_marked_low": marked,
            "debrief": debrief,
        }
    except Exception as exc:  # noqa: BLE001
        msg = _safe_err(exc)
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
            error=_safe_err(exc),
        )
        raise
    finally:
        db.close()


async def disk_inbox_router(ctx, job_id: str) -> dict:
    """Route files from Disk _inbox to vacancy folders via AI."""
    jid = uuid.UUID(job_id)
    db = SessionLocal()
    try:
        job = job_svc.get_job(db, jid)
        if not job:
            raise RuntimeError("Job not found")
        job_svc.update_job(
            db, jid, status="running", progress_pct=10, progress_label="Роутинг inbox…"
        )
        if job_svc.is_cancelled(db, jid):
            return {"ok": False, "cancelled": True}

        def _run():
            local = SessionLocal()
            try:
                from app.services.disk_inbox_router import process_inbox

                return process_inbox(local, limit=int((job.payload or {}).get("limit") or 20))
            finally:
                local.close()

        result = await asyncio.to_thread(_run)
        job_svc.update_job(
            db,
            jid,
            status="completed",
            progress_pct=100,
            progress_label=(
                f"Inbox: routed {result.get('routed', 0)}, "
                f"unsorted {result.get('unsorted', 0)}, errors {result.get('errors', 0)}"
            ),
            payload_patch=result,
            result_ref="disk_inbox:ok",
        )
        return {"ok": True, **result}
    except Exception as exc:  # noqa: BLE001
        job_svc.update_job(
            db,
            jid,
            status="failed",
            progress_label="Ошибка inbox-роутинга",
            error=_safe_err(exc),
        )
        raise
    finally:
        db.close()


async def vacancy_docs_from_materials(ctx, job_id: str) -> dict:
    """Transcribe/extract materials → generate vacancy docs pack → apply + history."""
    jid = uuid.UUID(job_id)
    db = SessionLocal()
    try:
        import shutil
        from pathlib import Path

        from app.db import models
        from app.services.source_extract import classify_path, extract_text_from_path
        from app.services.transcription import (
            cleanup_transcript_text,
            resolve_direct_url,
            download_media,
            get_yandex_download_url,
            get_yandex_public_meta,
            parse_yandex_link,
            transcribe_from_path,
            transcribe_from_url,
        )
        from app.services.vacancy_docs_pack import (
            apply_pack_to_vacancy,
            generate_package_from_sources,
            profile_text_from_vacancy,
            structure_meeting_brief,
        )
        from app.services.yandex_public import is_yandex_pdf, is_yandex_video_or_audio
        from app.services.pdf_extract import extract_text_from_pdf_url, download_url_bytes
        from app.services.source_extract import extract_text_from_bytes

        settings = get_settings()
        job = job_svc.get_job(db, jid)
        if not job:
            raise RuntimeError("Job not found")
        payload = dict(job.payload or {})
        vacancy_id = int(job.vacancy_id or payload.get("vacancy_id") or 0)
        if not vacancy_id:
            raise RuntimeError("Нужен vacancy_id")
        vacancy = db.get(models.Vacancy, vacancy_id)
        if not vacancy:
            raise RuntimeError(f"Вакансия {vacancy_id} не найдена")

        upload_dir = str(payload.get("upload_dir") or "").strip()
        file_paths = [str(p) for p in (payload.get("file_paths") or []) if str(p).strip()]
        source_urls = [str(u).strip() for u in (payload.get("source_urls") or []) if str(u).strip()]
        hr_instructions = str(payload.get("hr_instructions") or "").strip()
        use_existing_profile = bool(payload.get("use_existing_profile", True))
        flags = payload.get("doc_flags") if isinstance(payload.get("doc_flags"), dict) else {}
        doc_flags = {
            "profile": bool(flags.get("profile", True)),
            "questions": bool(flags.get("questions", True)),
            "vacancy_text": bool(flags.get("vacancy_text", True)),
            "keywords": bool(flags.get("keywords", True)),
        }

        def _prog(pct: int, label: str) -> None:
            job_svc.update_job(db, jid, progress_pct=pct, progress_label=label)

        if job_svc.is_cancelled(db, jid):
            return {"ok": False, "cancelled": True}

        job_svc.update_job(db, jid, status="running", progress_pct=5, progress_label="Сбор материалов…")

        supplemental: list[tuple[str, str]] = []
        transcripts: list[str] = []
        sources_used: list[str] = []

        sk = dict(
            api_key=settings.yandex_api_key,
            bucket=settings.yandex_bucket_name,
            access_key=settings.yandex_access_key_id,
            secret_key=settings.yandex_secret_access_key,
            ffmpeg_binary=settings.ffmpeg_binary or "",
        )

        # Local uploads
        for idx, path in enumerate(file_paths):
            if job_svc.is_cancelled(db, jid):
                return {"ok": False, "cancelled": True}
            p = Path(path)
            if not p.exists():
                continue
            kind = classify_path(p)
            label = p.name
            _prog(10 + min(40, idx * 8), f"Обработка файла: {label}")
            if kind == "media":
                raw = await asyncio.to_thread(
                    lambda path=str(p), label=label: transcribe_from_path(
                        path, **sk, source_label=label, on_progress=None
                    )
                )
                text = cleanup_transcript_text(raw.get("transcript") or "", settings)
                if text:
                    transcripts.append(text)
                    supplemental.append((f"Расшифровка: {label}", text))
                    sources_used.append(f"media:{label}")
            else:
                text = await asyncio.to_thread(extract_text_from_path, p)
                if text.strip():
                    supplemental.append((f"Документ: {label}", text))
                    sources_used.append(f"doc:{label}")

        # URLs (Yandex Disk / direct)
        for idx, url in enumerate(source_urls):
            if job_svc.is_cancelled(db, jid):
                return {"ok": False, "cancelled": True}
            _prog(50 + min(20, idx * 5), f"Обработка ссылки {idx + 1}…")
            is_yandex = url.startswith("yadisk:") or "disk.yandex" in url or "yadi.sk" in url
            media_like = False
            if is_yandex:
                root, path = parse_yandex_link(url)
                meta = get_yandex_public_meta(root or url, path=path or None)
                if meta and is_yandex_video_or_audio(meta):
                    media_like = True
                elif meta and is_yandex_pdf(meta):
                    text = extract_text_from_pdf_url(url)
                    if text.strip():
                        supplemental.append((f"Документ по ссылке: {url[:80]}", text))
                        sources_used.append(f"url_pdf:{url[:60]}")
                    continue
            # Guess media by extension
            lower = url.lower()
            if any(lower.endswith(ext) for ext in (".mp3", ".mp4", ".wav", ".webm", ".m4a", ".mov", ".mkv", ".ogg")):
                media_like = True
            if media_like or (is_yandex and media_like):
                raw = await asyncio.to_thread(
                    lambda u=url: transcribe_from_url(u, **sk, on_progress=None)
                )
                text = cleanup_transcript_text(raw.get("transcript") or "", settings)
                if text:
                    transcripts.append(text)
                    supplemental.append((f"Расшифровка по ссылке", text))
                    sources_used.append(f"url_media:{url[:60]}")
            else:
                # Try download + extract as document
                try:
                    direct = resolve_direct_url(url)
                    content = await asyncio.to_thread(download_url_bytes, direct, timeout=180)
                    name = Path(url.split("?")[0]).name or "download.bin"
                    text = extract_text_from_bytes(name, content)
                    if not text.strip() and content.lstrip().startswith(b"%PDF"):
                        text = extract_text_from_pdf_url(url)
                    if text.strip():
                        supplemental.append((f"Документ по ссылке: {name}", text))
                        sources_used.append(f"url_doc:{url[:60]}")
                    else:
                        # Last resort: treat as media
                        raw = await asyncio.to_thread(
                            lambda u=url: transcribe_from_url(u, **sk, on_progress=None)
                        )
                        text = cleanup_transcript_text(raw.get("transcript") or "", settings)
                        if text:
                            transcripts.append(text)
                            supplemental.append((f"Расшифровка по ссылке", text))
                            sources_used.append(f"url_media_fallback:{url[:60]}")
                except Exception as exc:  # noqa: BLE001
                    sources_used.append(f"url_error:{type(exc).__name__}")

        notes = str(payload.get("notes") or "").strip()
        if notes:
            supplemental.append(("Заметки HR", notes))

        if not supplemental and not (use_existing_profile and profile_text_from_vacancy(vacancy)):
            raise RuntimeError("Нет материалов для генерации (файлы/ссылки/профиль пусты)")

        profile_text = profile_text_from_vacancy(vacancy) if use_existing_profile else ""
        extra_profile = str(payload.get("profile_text") or "").strip()
        if extra_profile:
            profile_text = extra_profile if not profile_text else profile_text + "\n\n" + extra_profile

        _prog(75, "Генерация пакета документов…")
        pack = await asyncio.to_thread(
            lambda: generate_package_from_sources(
                vacancy_title=vacancy.title,
                profile_text=profile_text,
                supplemental_blocks=supplemental,
                hr_instructions=hr_instructions,
                doc_flags=doc_flags,
                settings=settings,
            )
        )

        joined_transcript = "\n\n---\n\n".join(transcripts)
        brief = {}
        if joined_transcript.strip():
            _prog(88, "Структурирование расшифровки…")
            brief = await asyncio.to_thread(
                lambda: structure_meeting_brief(
                    joined_transcript, settings=settings, title=vacancy.title
                )
            )

        _prog(95, "Сохранение в вакансию…")
        apply_pack_to_vacancy(
            db,
            vacancy,
            pack,
            meeting_brief=brief,
            transcript_clean=joined_transcript,
            source_label="; ".join(sources_used[:12]),
        )

        # cleanup upload dir
        if upload_dir:
            try:
                shutil.rmtree(upload_dir, ignore_errors=True)
            except Exception:  # noqa: BLE001
                pass

        job_svc.update_job(
            db,
            jid,
            status="completed",
            progress_pct=100,
            progress_label="Документы обновлены",
            payload_patch={
                "sources": sources_used,
                "conflicts": pack.get("conflicts") or [],
                "meeting_brief": brief,
                "applied_keys": [k for k in ("profile", "vacancy_text", "questions", "keywords") if k in pack],
            },
            result_ref=f"vacancy_docs:{vacancy_id}",
        )
        return {"ok": True, "vacancy_id": vacancy_id, "sources": sources_used}
    except Exception as exc:  # noqa: BLE001
        msg = _safe_err(exc)
        if msg == "Отменено" or job_svc.is_cancelled(db, jid):
            job_svc.update_job(db, jid, status="cancelled", progress_label="Отменено")
            return {"ok": False, "cancelled": True}
        job_svc.update_job(
            db,
            jid,
            status="failed",
            progress_label="Ошибка генерации документов",
            error=msg,
        )
        raise
    finally:
        db.close()
