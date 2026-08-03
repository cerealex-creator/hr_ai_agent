"""Flatten HH resume JSON → plain text for AI eval (no contacts required)."""

from __future__ import annotations

from typing import Any


def _join(parts: list[str]) -> str:
    return "\n".join(p for p in parts if p and str(p).strip())


def _exp_block(item: dict[str, Any]) -> str:
    company = (item.get("company") or "").strip()
    position = (item.get("position") or "").strip()
    start = (item.get("start") or "").strip()
    end = (item.get("end") or "").strip() or "н.в."
    desc = (item.get("description") or "").strip()
    head = " · ".join(x for x in (position, company, f"{start}–{end}") if x)
    return _join([head, desc])


def resume_to_text(resume: dict[str, Any]) -> str:
    """Build evaluation text from HH resume object. Skips phones/emails/FIO if present."""
    if not isinstance(resume, dict):
        return ""
    parts: list[str] = []

    title = (resume.get("title") or "").strip()
    if title:
        parts.append(f"Желаемая должность: {title}")

    area = resume.get("area") or {}
    if isinstance(area, dict) and area.get("name"):
        parts.append(f"Регион: {area['name']}")

    salary = resume.get("salary") or {}
    if isinstance(salary, dict) and salary.get("amount"):
        cur = salary.get("currency") or ""
        parts.append(f"Зарплатные ожидания: {salary['amount']} {cur}".strip())

    total = resume.get("total_experience") or {}
    if isinstance(total, dict) and total.get("months") is not None:
        months = int(total["months"])
        parts.append(f"Общий опыт: {months // 12} лет {months % 12} мес.")

    age = resume.get("age")
    if age is not None:
        parts.append(f"Возраст: {age}")

    skills = resume.get("skill_set") or resume.get("skills")
    if isinstance(skills, list) and skills:
        parts.append("Навыки: " + ", ".join(str(s) for s in skills if s))
    elif isinstance(skills, str) and skills.strip():
        parts.append(f"Навыки: {skills.strip()}")

    experience = resume.get("experience") or []
    if isinstance(experience, list) and experience:
        parts.append("Опыт работы:")
        for item in experience:
            if isinstance(item, dict):
                block = _exp_block(item)
                if block:
                    parts.append(block)
                    parts.append("")

    education = resume.get("education") or {}
    if isinstance(education, dict):
        primary = education.get("primary") or []
        if isinstance(primary, list) and primary:
            parts.append("Образование:")
            for ed in primary:
                if not isinstance(ed, dict):
                    continue
                name = (ed.get("name") or "").strip()
                org = (ed.get("organization") or "").strip()
                year = ed.get("year")
                line = " · ".join(str(x) for x in (name, org, year) if x)
                if line:
                    parts.append(line)

    about = (resume.get("skills") if isinstance(resume.get("skills"), str) else None) or ""
    # HH sometimes puts free-form "about" in skill string field separately from skill_set
    if about and "Навыки:" not in "\n".join(parts):
        parts.append(f"О себе / навыки (текст):\n{about.strip()}")

    return _join(parts).strip()


def resume_card_summary(item: dict[str, Any]) -> dict[str, Any]:
    """Safe fields from search hit or full resume (never include contact actions usage)."""
    area = item.get("area") or {}
    salary = item.get("salary") or {}
    url = ""
    alt = item.get("alternate_url") or ""
    if alt:
        url = alt
    elif item.get("id"):
        url = f"https://hh.ru/resume/{item['id']}"
    return {
        "hh_resume_id": str(item.get("id") or ""),
        "title": (item.get("title") or "").strip(),
        "url": url,
        "area": area.get("name") if isinstance(area, dict) else None,
        "age": item.get("age"),
        "salary_amount": salary.get("amount") if isinstance(salary, dict) else None,
        "salary_currency": salary.get("currency") if isinstance(salary, dict) else None,
        "updated_at": item.get("updated_at") or item.get("created_at"),
    }
