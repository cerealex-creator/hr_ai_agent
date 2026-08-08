"""Normalize interview questionnaire items (v2, no Streamlit)."""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

HR_RATING_LABELS = {
    "good": "Хорошо",
    "satisfactory": "Удовлетворительно",
    "doubtful": "Сомнительно",
    "no": "Нет",
}

_LEGACY_HR_RATING_MAP = {
    "ok": "satisfactory",
    "doubt_ok": "doubtful",
    "норм": "satisfactory",
    "хорошо": "good",
    "сомнительно": "doubtful",
    "нет": "no",
}


def normalize_hr_rating(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    key = raw.lower()
    if key in HR_RATING_LABELS:
        return key
    mapped = _LEGACY_HR_RATING_MAP.get(key)
    if mapped:
        return mapped
    return ""


def looks_like_pipe_questionnaire_dump(text: str) -> bool:
    t = (text or "").strip()
    if "|" not in t or "\n" not in t:
        return False
    markers = (
        "Что уже есть в резюме",
        "Желательный результат",
        "Сомн, но ок",
        "Сомнительно",
        "Норм",
    )
    hits = sum(1 for m in markers if m in t)
    if hits >= 2:
        return True
    return t.count("|") >= 20 and ("Вопрос" in t or "1.0 |" in t or "1 |" in t)


def recover_questionnaire_from_pipe_dump(text: str) -> list[dict[str, Any]]:
    raw = (text or "").replace("\r\n", "\n").strip()
    if not raw:
        return []
    if raw.startswith("["):
        try:
            parsed = json.loads(raw)
            if (
                isinstance(parsed, list)
                and len(parsed) == 1
                and isinstance(parsed[0], dict)
                and looks_like_pipe_questionnaire_dump(str(parsed[0].get("вопрос") or ""))
            ):
                raw = str(parsed[0].get("вопрос") or "")
            elif isinstance(parsed, list) and parsed and all(isinstance(x, dict) for x in parsed):
                return []
        except json.JSONDecodeError:
            pass

    merged_lines: list[str] = []
    for ln in raw.split("\n"):
        line = ln.strip()
        if not line:
            continue
        starts_row = bool(re.match(r"^\d+\.?\d*\s*\|", line)) or line.startswith("№")
        if starts_row or not merged_lines:
            merged_lines.append(line)
        else:
            merged_lines[-1] = merged_lines[-1].rstrip() + " " + line.lstrip()

    items: list[dict[str, Any]] = []
    for line in merged_lines:
        if "|" not in line:
            continue
        if line.startswith("№") or (
            "Что уже есть в резюме" in line and "Желательный результат" in line
        ):
            continue
        parts = [p.strip() for p in line.split("|")]
        if not parts:
            continue
        if parts[0].replace(".", "", 1).isdigit() or (
            parts[0].endswith(".0") and parts[0][:-2].isdigit()
        ):
            parts = parts[1:]
        if not parts:
            continue
        question = (parts[0] or "").strip()
        if not question or question.lower().startswith("итог"):
            continue
        resume_hint = parts[1].strip() if len(parts) > 1 else ""
        answer = parts[2].strip() if len(parts) > 2 else ""
        example = parts[3].strip() if len(parts) > 3 else ""
        flag_tokens = {"false", "true", "0", "1", ""}
        if not example and len(parts) > 2:
            for p in reversed(parts[1:]):
                if p.strip().lower() not in flag_tokens:
                    example = p.strip()
                    break
        items.append(
            {
                "вопрос": question,
                "уточняющие_вопросы": [],
                "уточнения_по_резюме": [],
                "проверяет_требование": "",
                "категория": "",
                "пример_ответа": example,
                "в_резюме": resume_hint,
                "ответ": answer,
                "ответ_кандидата": "",
                "оценка_ии": "",
                "пояснение_ии": "",
                "оценка_hr": "",
                "оценка": "",
            }
        )
    return items


def normalize_questionnaire_list(items: Any) -> list[dict[str, Any]]:
    if isinstance(items, str):
        text = items.strip()
        if not text:
            return []
        if looks_like_pipe_questionnaire_dump(text):
            recovered = recover_questionnaire_from_pipe_dump(text)
            items = recovered if recovered else [{"вопрос": text}]
        elif text.startswith("["):
            try:
                parsed = json.loads(text)
                items = parsed if isinstance(parsed, list) else [{"вопрос": text}]
            except json.JSONDecodeError:
                items = [{"вопрос": text}]
        else:
            items = [{"вопрос": line.strip()} for line in text.splitlines() if line.strip()]

    if not isinstance(items, list):
        return []

    if (
        len(items) == 1
        and isinstance(items[0], dict)
        and looks_like_pipe_questionnaire_dump(str(items[0].get("вопрос") or ""))
    ):
        recovered = recover_questionnaire_from_pipe_dump(str(items[0].get("вопрос") or ""))
        if recovered:
            items = recovered

    result: list[dict[str, Any]] = []
    for q in items:
        if isinstance(q, str):
            if looks_like_pipe_questionnaire_dump(q):
                recovered = recover_questionnaire_from_pipe_dump(q)
                if recovered:
                    result.extend(recovered)
                    continue
            item = {
                "вопрос": q,
                "уточняющие_вопросы": [],
                "уточнения_по_резюме": [],
                "проверяет_требование": "",
                "категория": "",
                "пример_ответа": "",
                "в_резюме": "",
                "ответ": "",
                "ответ_кандидата": "",
                "оценка_ии": "",
                "пояснение_ии": "",
                "оценка_hr": "",
                "оценка": "",
                "_qid": "",
            }
        elif isinstance(q, dict):
            followups = q.get("уточняющие_вопросы", q.get("followups", []))
            if isinstance(followups, str):
                followups = [followups] if followups.strip() else []
            rating = normalize_hr_rating(q.get("оценка_hr", q.get("оценка", q.get("rating", ""))))
            item = {
                "вопрос": q.get("вопрос", q.get("question", "")),
                "уточняющие_вопросы": (
                    [str(f) for f in followups] if isinstance(followups, list) else []
                ),
                "уточнения_по_резюме": [
                    str(f)
                    for f in (q.get("уточнения_по_резюме") or q.get("resume_followups") or [])
                    if str(f).strip()
                ],
                "проверяет_требование": q.get("проверяет_требование", q.get("requirement", "")),
                "категория": q.get("категория", q.get("category", "")),
                "пример_ответа": q.get("пример_ответа", q.get("example", "")),
                "в_резюме": q.get("в_резюме", q.get("resume_hint", "")),
                "ответ": q.get("ответ", q.get("answer", "")),
                "ответ_кандидата": q.get("ответ_кандидата", q.get("candidate_answer", "")),
                "оценка_ии": q.get("оценка_ии", q.get("ai_rating", "")),
                "пояснение_ии": q.get("пояснение_ии", q.get("ai_note", "")),
                "оценка_hr": rating,
                "оценка": rating,
                "_qid": q.get("_qid", ""),
                "is_manual": bool(q.get("is_manual")),
            }
        else:
            continue
        if not str(item.get("вопрос") or "").strip():
            continue
        result.append(item)
    return ensure_question_ids(result)


def ensure_question_ids(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for q in items or []:
        item = dict(q)
        if not str(item.get("_qid") or "").strip():
            item["_qid"] = uuid.uuid4().hex[:8]
        rating = normalize_hr_rating(item.get("оценка_hr", item.get("оценка", "")))
        item["оценка_hr"] = rating
        item["оценка"] = rating
        if "is_manual" in item:
            item["is_manual"] = bool(item.get("is_manual"))
        out.append(item)
    return out


def vacancy_questions_as_list(documents: dict | None) -> list[dict[str, Any]]:
    docs = documents or {}
    raw = docs.get("questions")
    if raw is None:
        raw = docs.get("опросник")
    return normalize_questionnaire_list(raw)
