"""ИИ: извлечение данных из резюме и оценка на первичной стадии."""

import json
import re
import uuid
from io import BytesIO
from urllib.parse import quote

import requests
import PyPDF2

from ai_helpers import (
    create_chat_completion,
    get_char_limit,
    parse_ai_json_response,
    trim_profile_for_eval,
    trim_text,
)

RESUME_EXTRACT_SYSTEM = """Ты — HR-ассистент. Извлеки структурированные данные из текста резюме.
Верни ТОЛЬКО валидный JSON без markdown:
{
  "full_name": "ФИО полностью",
  "phone": "телефон в формате 7 999 999-99-99 или Нет информации",
  "age": "возраст числом или Нет информации",
  "metro": "станция метро или пустая строка",
  "city": "город проживания или Нет информации",
  "salary": "ожидаемая зарплата числом или Нет информации"
}
Правила:
- Если данных нет — пиши "Нет информации" (для metro — пустая строка).
- Телефон нормализуй к виду 7 XXX XXX-XX-XX, если возможно.
- Возраст — только число лет без слова «лет».
- Зарплата — только число без валюты."""

RESUME_EXTRACT_CONTROL_WORD_EXTRA = """
Дополнительно (только если передано КОНТРОЛЬНОЕ СЛОВО):
Найди сопроводительное письмо в тексте (блок «О себе» / cover letter / сопроводительное — НЕ опыт работы и НЕ навыки).
Ищи контрольное слово/фразу ТОЛЬКО в сопроводительном письме.
Допустима семантика «почти точное»: опечатки, раскладка, транслит (YourBox / YouBox / Ёрбокс).
Добавь в JSON поля:
  "control_word_status": "exact" | "fuzzy" | "missing" | "no_cover_letter",
  "control_word_match": "как написал кандидат или пустая строка",
  "control_word_note": "кратко: точное совпадение / найдено с опечаткой «…» / не найдено / нет письма"
exact — совпадение без смысловых искажений (регистр не важен).
fuzzy — явно то же задание, но с ошибкой/небрежностью (укажи в note).
missing — письмо есть, слова нет.
no_cover_letter — сопроводительного письма нет.
Не ищи слово в остальных частях резюме.
"""

RESUME_EVAL_SYSTEM = """Ты — опытный HR-директор. Оцени соответствие резюме профилю должности на этапе холодного отбора.
Шкала rating: 0–4 (целое число).
Верни ТОЛЬКО JSON:
{
  "rating": 3,
  "comment_sections": {
    "соответствие": "1–3 предложения: насколько подходит под профиль",
    "опыт_и_навыки": "1–3 предложения по опыту и hard/soft skills",
    "риски": ["риск 1", "риск 2"],
    "проверить_на_интервью": ["что уточнить на интервью"],
    "итог": "1–2 предложения — краткий вердикт"
  },
  "strengths": ["..."],
  "weaknesses": ["..."]
}

Структура comment_sections обязательна (как разделы профиля должности): отдельные пункты, без сплошного абзаца.
Поле "comment" не используй — только comment_sections.

Дополнительно проанализируй риски (отрази в «риски» / weaknesses):
- Частая смена работы, неясные или противоречивые причины ухода, переход с фриланса/самозанятости без логики в резюме.
- Длительные пробелы в опыте без пояснения — отметь необходимость выяснить причину на интервью.
- Признаки излишней требовательности (только идеальные условия, много жёстких «не готов» без гибкости).
На этапе резюме лояльность, адекватность и управляемость оцени предварительно по косвенным признакам; явно укажи в «проверить_на_интервью».

Если передан КОММЕНТАРИЙ HR — обязательно учти его: это живые замечания рекрутера после контакта с кандидатом; согласуй оценку с ними и отрази в comment_sections."""

AI_COMMENT_SECTION_ORDER = (
    ("соответствие", "Соответствие"),
    ("опыт_и_навыки", "Опыт и навыки"),
    ("риски", "Риски"),
    ("проверить_на_интервью", "Проверить на интервью"),
    ("итог", "Итог"),
)

QUESTIONNAIRE_ITEM_SCHEMA = """{
  "вопрос": "основной вопрос в разговорной форме",
  "уточняющие_вопросы": ["уточнение 1"],
  "проверяет_требование": "какой пункт профиля проверяем",
  "категория": "hard_skills | soft_skills | experience | motivation | reliability",
  "пример_ответа": "реалистичный ответ сильного кандидата"
}"""

CANDIDATE_QUESTIONNAIRE_SYSTEM = (
    """Ты — HR-директор. Сформируй персональный опросник для первичного собеседования КОНКРЕТНОГО кандидата.

Правила:
1. Оптимально 6–8 ОСНОВНЫХ вопросов. Максимум 10 — только если критичные пробелы невозможно закрыть меньшим числом.
2. Если передан ТЕКУЩИЙ ОПРОСНИК вакансии — возьми из него самые важные вопросы, ОБЪЕДИНЯЯ повторяющиеся по смыслу; не копируй слепо все пункты.
3. ОБЯЗАТЕЛЬНО включи четыре блока (каждый — один основной вопрос с уточняющими):
   — причина поиска/ухода с последнего места или с фриланса (пробелы в опыте);
   — что вдохновляет на работе;
   — что расстраивает и заставляет задуматься об уходе;
   — обратная связь от прошлых работодателей (контакты или «хорошо ли расстались»).
4. Добавь вопросы по пробелам резюме и слабым сторонам из оценки ИИ — только если они не дублируют п.2–3.
5. Не дублируй смысл; мелочи — в уточняющие, не в отдельные основные вопросы.
6. Стиль беседы: «Был ли у Вас опыт ...? Расскажите на примере», не допрос.
7. К каждому основному вопросу — 1–3 уточняющих вопроса.
8. категория: hard_skills / soft_skills / experience / motivation / reliability.

Верни ТОЛЬКО JSON:
{"опросник": ["""
    + QUESTIONNAIRE_ITEM_SCHEMA
    + """]}"""
)

HR_RATING_LABELS = {
    "good": "Хорошо",
    "satisfactory": "Удовлетворительно",
    "doubtful": "Сомнительно",
    "no": "Нет",
}
_LEGACY_HR_RATING_MAP = {
    "ok": "satisfactory",
    "doubt_ok": "doubtful",
    "no": "no",
}


def normalize_hr_rating(value):
    raw = (value or "").strip()
    if not raw:
        return ""
    if raw in _LEGACY_HR_RATING_MAP:
        return _LEGACY_HR_RATING_MAP[raw]
    return raw if raw in HR_RATING_LABELS else ""


def looks_like_pipe_questionnaire_dump(text):
    """
    True if text is a stringified old interview grid
    (№ | Вопрос | Что уже есть… | False | False | False).
    """
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


def recover_questionnaire_from_pipe_dump(text):
    """Разбирает дамп старой таблицы опросника → список вопросов."""
    raw = (text or "").replace("\r\n", "\n").strip()
    if not raw:
        return []
    # Sometimes the dump is wrapped in JSON [{"вопрос": "№ | ..."}]
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
                # already structured — leave to normalize_questionnaire_list
                return []
        except json.JSONDecodeError:
            pass

    # Join rows broken by newlines inside the question cell
    merged_lines = []
    for ln in raw.split("\n"):
        line = ln.strip()
        if not line:
            continue
        starts_row = bool(re.match(r"^\d+\.?\d*\s*\|", line)) or line.startswith("№")
        if starts_row or not merged_lines:
            merged_lines.append(line)
        else:
            merged_lines[-1] = merged_lines[-1].rstrip() + " " + line.lstrip()

    items = []
    for line in merged_lines:
        if "|" not in line:
            continue
        # header
        if line.startswith("№") or (
            "Что уже есть в резюме" in line and "Желательный результат" in line
        ):
            continue

        parts = [p.strip() for p in line.split("|")]
        if not parts:
            continue
        # drop pandas-like index 1.0 / 2.0
        if parts[0].replace(".", "", 1).isdigit() or (
            parts[0].endswith(".0") and parts[0][:-2].isdigit()
        ):
            parts = parts[1:]
        if not parts:
            continue
        question = (parts[0] or "").strip()
        if not question or question.lower().startswith("итог"):
            continue

        # Columns after question: в_резюме | ответ | желательный | flags...
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
                "оценка_hr": "",
                "оценка": "",
            }
        )
    return items


def normalize_questionnaire_list(items):
    if isinstance(items, str):
        text = items.strip()
        if not text:
            return []
        if looks_like_pipe_questionnaire_dump(text):
            recovered = recover_questionnaire_from_pipe_dump(text)
            if recovered:
                items = recovered
            else:
                items = [{"вопрос": text}]
        elif text.startswith("["):
            try:
                parsed = json.loads(text)
                items = parsed if isinstance(parsed, list) else [{"вопрос": text}]
            except json.JSONDecodeError:
                items = [{"вопрос": text}]
        else:
            items = [{"вопрос": text}]

    if not isinstance(items, list):
        return []

    # Expand a single pipe-dump "question" accidentally saved as one row
    if (
        len(items) == 1
        and isinstance(items[0], dict)
        and looks_like_pipe_questionnaire_dump(str(items[0].get("вопрос") or ""))
    ):
        recovered = recover_questionnaire_from_pipe_dump(str(items[0].get("вопрос") or ""))
        if recovered:
            items = recovered
    elif (
        len(items) == 1
        and isinstance(items[0], str)
        and looks_like_pipe_questionnaire_dump(items[0])
    ):
        recovered = recover_questionnaire_from_pipe_dump(items[0])
        if recovered:
            items = recovered

    result = []
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
                "проверяет_требование": "",
                "категория": "",
                "пример_ответа": "",
            }
        elif isinstance(q, dict):
            followups = q.get("уточняющие_вопросы", q.get("followups", []))
            if isinstance(followups, str):
                followups = [followups] if followups.strip() else []
            rating = normalize_hr_rating(q.get("оценка_hr", q.get("оценка", q.get("rating", ""))))
            item = {
                "вопрос": q.get("вопрос", q.get("question", "")),
                "уточняющие_вопросы": [str(f) for f in followups] if isinstance(followups, list) else [],
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
                "оценка_hr": rating,
                "оценка": rating,
                "_qid": q.get("_qid", ""),
            }
        else:
            continue
        if not item.get("_qid"):
            item["_qid"] = uuid.uuid4().hex[:8]
        result.append(item)
    return [q for q in result if (q.get("вопрос") or "").strip()]


def format_phone(phone):
    if not phone or str(phone).strip().lower() in ("нет информации", "—", "-", ""):
        return "Нет информации"
    digits = re.sub(r"\D", "", str(phone))
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    if len(digits) == 10:
        digits = "7" + digits
    if len(digits) == 11 and digits.startswith("7"):
        return f"{digits[0]} {digits[1:4]} {digits[4:7]}-{digits[7:9]}-{digits[9:11]}"
    return str(phone).strip() or "Нет информации"


def format_age_location(age, metro, city):
    age_part = "Нет информации"
    if age and str(age).strip().lower() not in ("нет информации", "", "—"):
        age_str = str(age).strip()
        if age_str.isdigit():
            n = int(age_str)
            if n % 10 == 1 and n % 100 != 11:
                suffix = "год"
            elif 2 <= n % 10 <= 4 and (n % 100 < 10 or n % 100 >= 20):
                suffix = "года"
            else:
                suffix = "лет"
            age_part = f"{n} {suffix}"
        else:
            age_part = age_str

    metro = (metro or "").strip()
    city = (city or "").strip()
    if metro and metro.lower() not in ("нет информации", "—"):
        loc = f"м. {metro}" if not metro.lower().startswith("м.") else metro
    elif city and city.lower() not in ("нет информации", "—"):
        loc = city
    else:
        loc = "Нет информации"

    if age_part == "Нет информации" and loc == "Нет информации":
        return "Нет информации"
    if age_part == "Нет информации":
        return loc
    if loc == "Нет информации":
        return age_part
    return f"{age_part} {loc}"


def format_salary(salary):
    if not salary or str(salary).strip().lower() in ("нет информации", "", "—"):
        return "Нет информации"
    digits = re.sub(r"\D", "", str(salary))
    if digits:
        return f"{int(digits):,}".replace(",", " ")
    return str(salary).strip()


def format_ai_comment_from_sections(sections):
    """Plain-text fallback from structured comment_sections."""
    if not isinstance(sections, dict) or not sections:
        return ""
    parts = []
    used = set()
    for key, title in AI_COMMENT_SECTION_ORDER:
        if key not in sections:
            continue
        used.add(key)
        val = sections.get(key)
        if val is None or val == "":
            continue
        if isinstance(val, list):
            body = "\n".join(f"- {item}" for item in val if str(item).strip())
        else:
            body = str(val).strip()
        if body:
            parts.append(f"{title}\n{body}")
    for key, val in sections.items():
        if key in used or val is None or val == "":
            continue
        if isinstance(val, list):
            body = "\n".join(f"- {item}" for item in val if str(item).strip())
        else:
            body = str(val).strip()
        if body:
            parts.append(f"{key}\n{body}")
    return "\n\n".join(parts).strip()


def normalize_ai_comment_sections(raw_sections, legacy_comment=""):
    """Return (sections_dict, plain_comment)."""
    sections = raw_sections if isinstance(raw_sections, dict) else {}
    if not sections and (legacy_comment or "").strip():
        sections = {"итог": str(legacy_comment).strip()}
    plain = format_ai_comment_from_sections(sections) or (legacy_comment or "").strip()
    return sections, plain


def extract_data_from_resume(resume_text, client, config, control_word=None):
    if not resume_text or not resume_text.strip():
        raise ValueError("Пустой текст резюме")
    resume_limit = get_char_limit(config, "resume", 8000)
    system = RESUME_EXTRACT_SYSTEM
    user = f"Текст резюме:\n{trim_text(resume_text, resume_limit)}"
    word = (control_word or "").strip()
    if word:
        system = RESUME_EXTRACT_SYSTEM + "\n" + RESUME_EXTRACT_CONTROL_WORD_EXTRA
        user += f"\n\nКОНТРОЛЬНОЕ СЛОВО (искать только в сопроводительном письме): {word}"
    response = create_chat_completion(
        client,
        config,
        "extract",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.1,
    )
    data = parse_ai_json_response(response.choices[0].message.content)
    out = {
        "name": data.get("full_name") or "Нет информации",
        "phone": format_phone(data.get("phone")),
        "age": data.get("age") if str(data.get("age", "")).strip() else "",
        "city": data.get("city") if str(data.get("city", "")).strip() else "",
        "metro": data.get("metro") if str(data.get("metro", "")).strip() else "",
        "age_location": format_age_location(data.get("age"), data.get("metro"), data.get("city")),
        "salary_expected": format_salary(data.get("salary")),
    }
    if word:
        status = (data.get("control_word_status") or "").strip().lower()
        if status not in ("exact", "fuzzy", "missing", "no_cover_letter"):
            status = "missing"
        out["control_word_status"] = status
        out["control_word_match"] = (data.get("control_word_match") or "").strip()
        out["control_word_note"] = (data.get("control_word_note") or "").strip()
    return out


RESUME_HINTS_SYSTEM = """Ты — HR-ассистент. По тексту резюме заполни для каждого вопроса опросника колонку «Что уже есть в резюме».

Правила:
- 1–3 коротких предложения: что резюме уже говорит по теме вопроса, с конкретными фактами из резюме.
- Если в резюме нет ничего по теме — напиши «Нет данных в резюме».
- Не выдумывай факты, которых нет в резюме.

Верни ТОЛЬКО JSON:
{"подсказки": ["текст для вопроса 1", "текст для вопроса 2", ...]}

Число элементов в подсказках ДОЛЖНО совпадать с числом вопросов."""


def enrich_questionnaire_with_resume_hints(resume_text, questionnaire, client, config):
    """Заполняет поле «в_резюме» для каждого вопроса персонального опросника."""
    items = normalize_questionnaire_list(questionnaire)
    if not items or not (resume_text or "").strip():
        return items

    questions = [q.get("вопрос", "") for q in items]
    q_block = "\n".join(f"{i + 1}. {q}" for i, q in enumerate(questions))
    resume_limit = get_char_limit(config, "resume", 8000)

    response = create_chat_completion(
        client,
        config,
        "questionnaire",
        messages=[
            {"role": "system", "content": RESUME_HINTS_SYSTEM},
            {
                "role": "user",
                "content": (
                    f"РЕЗЮМЕ:\n{trim_text(resume_text, resume_limit)}\n\n"
                    f"ВОПРОСЫ ОПРОСНИКА:\n{q_block}\n\n"
                    "Заполни подсказки «Что уже есть в резюме» для каждого вопроса."
                ),
            },
        ],
        temperature=0.2,
        response_format={"type": "json_object"},
    )
    result = parse_ai_json_response(response.choices[0].message.content)
    hints = result.get("подсказки", [])
    if not isinstance(hints, list):
        hints = []

    for i, item in enumerate(items):
        if i < len(hints):
            item["в_резюме"] = str(hints[i]).strip()
        elif not (item.get("в_резюме") or "").strip():
            item["в_резюме"] = "Нет данных в резюме"
    return items


PERSONAL_FOLLOWUPS_SYSTEM = """Ты — HR-ассистент. Есть фиксированный опросник собеседования (основные вопросы менять нельзя) и резюме кандидата.

Для КАЖДОГО основного вопроса предложи 0–3 персональных уточняющих вопроса, которые:
- закрывают пробелы резюме по теме этого вопроса;
- уточняют противоречия, общие формулировки или «красные флаги»;
- НЕ повторяют дословно основной вопрос и не дублируют уже указанные в резюме факты;
- помогают проверить то, чего в резюме нет или что сформулировано расплывчато.

Если по теме вопроса резюме уже даёт полный ответ — верни пустой список [].

Верни ТОЛЬКО JSON:
{"уточнения_по_резюме": [["уточнение 1"], [], ...]}

Число внутренних списков ДОЛЖНО совпадать с числом основных вопросов, порядок — тот же."""


def copy_vacancy_questionnaire_template(base_questionnaire):
    """Копия шаблона опросника вакансии — одинаковые основные вопросы для всех кандидатов."""
    items = normalize_questionnaire_list(base_questionnaire or [])
    for item in items:
        item["уточнения_по_резюме"] = []
    return items


def _merge_personal_followups(items, followups_lists):
    for i, item in enumerate(items):
        raw = followups_lists[i] if i < len(followups_lists) else []
        if not isinstance(raw, list):
            raw = [raw] if raw else []
        personal = []
        for f in raw:
            text = str(f).strip()
            if text and text not in personal:
                personal.append(text)
        item["уточнения_по_резюме"] = personal[:5]
    return items


def enrich_questionnaire_with_personal_followups(
    resume_text,
    questionnaire,
    client,
    config,
    *,
    hr_comment="",
    eval_comment="",
    strengths=None,
    weaknesses=None,
):
    """Добавляет персональные уточнения по резюме к каждому вопросу шаблона."""
    items = normalize_questionnaire_list(questionnaire)
    if not items or not (resume_text or "").strip():
        return items

    questions = [q.get("вопрос", "") for q in items]
    q_block = "\n".join(f"{i + 1}. {q}" for i, q in enumerate(questions))
    resume_limit = get_char_limit(config, "resume", 8000)
    eval_comment_limit = get_char_limit(config, "eval_comment", 1500)

    user_parts = [
        f"РЕЗЮМЕ:\n{trim_text(resume_text, resume_limit)}",
        f"ОСНОВНЫЕ ВОПРОСЫ ОПРОСНИКА (не менять, только уточнения по резюме):\n{q_block}",
    ]
    if (eval_comment or "").strip():
        user_parts.append(
            f"КОММЕНТАРИЙ ИИ ПО РЕЗЮМЕ:\n{trim_text(eval_comment, eval_comment_limit)}"
        )
    if strengths:
        user_parts.append("СИЛЬНЫЕ СТОРОНЫ:\n" + "\n".join(f"- {s}" for s in (strengths or [])[:10]))
    if weaknesses:
        user_parts.append(
            "СЛАБЫЕ СТОРОНЫ / ПРОБЕЛЫ:\n" + "\n".join(f"- {w}" for w in (weaknesses or [])[:10])
        )
    hr_block = format_hr_comment_block(hr_comment, config)
    if hr_block:
        user_parts.append(hr_block.strip())
    user_parts.append(
        "Сформируй персональные уточняющие вопросы по резюме для каждого основного вопроса."
    )

    response = create_chat_completion(
        client,
        config,
        "questionnaire",
        messages=[
            {"role": "system", "content": PERSONAL_FOLLOWUPS_SYSTEM},
            {"role": "user", "content": "\n\n".join(user_parts)},
        ],
        temperature=0.3,
        response_format={"type": "json_object"},
    )
    result = parse_ai_json_response(response.choices[0].message.content)
    followups = result.get("уточнения_по_резюме", result.get("уточняющие", []))
    if not isinstance(followups, list):
        followups = []
    return _merge_personal_followups(items, followups)


def build_candidate_questionnaire_from_template(
    resume_text,
    base_questionnaire,
    client,
    config,
    *,
    hr_comment="",
    eval_comment="",
    strengths=None,
    weaknesses=None,
):
    """
    Опросник кандидата: основные вопросы = шаблон вакансии (одинаковые для всех),
    персонализация — колонка «В резюме» и блок «Уточнения по резюме».
    """
    questionnaire = copy_vacancy_questionnaire_template(base_questionnaire)
    if not questionnaire:
        raise ValueError(
            "Шаблон опросника вакансии пуст — заполните опросник в «Документы по вакансии»."
        )
    questionnaire = enrich_questionnaire_with_resume_hints(
        resume_text, questionnaire, client, config
    )
    questionnaire = enrich_questionnaire_with_personal_followups(
        resume_text,
        questionnaire,
        client,
        config,
        hr_comment=hr_comment,
        eval_comment=eval_comment,
        strengths=strengths,
        weaknesses=weaknesses,
    )
    return questionnaire


def format_hr_comment_block(hr_comment, config=None):
    text = (hr_comment or "").strip()
    if not text:
        return ""
    limit = get_char_limit(config, "hr_comment", 2000) if config else 2000
    return (
        "\nКОММЕНТАРИЙ HR (обязательно учти при оценке — замечания рекрутера после контакта с кандидатом):\n"
        f"{text[:limit]}\n"
    )


def evaluate_resume_with_ai(
    resume_text, vacancy_profile, job_title, client, config, hr_comment=""
):
    profile_block = trim_profile_for_eval(
        vacancy_profile,
        get_char_limit(config, "profile", 5000),
    )
    resume_limit = get_char_limit(config, "resume", 8000)
    hr_block = format_hr_comment_block(hr_comment, config)
    response = create_chat_completion(
        client,
        config,
        "resume_eval",
        messages=[
            {"role": "system", "content": RESUME_EVAL_SYSTEM},
            {
                "role": "user",
                "content": (
                    f"Должность: {job_title}\n\nПРОФИЛЬ:\n{profile_block}\n\n"
                    f"РЕЗЮМЕ:\n{trim_text(resume_text, resume_limit)}"
                    f"{hr_block}"
                ),
            },
        ],
        temperature=0.3,
        response_format={"type": "json_object"},
    )
    result = parse_ai_json_response(response.choices[0].message.content)
    rating = result.get("rating", 0)
    try:
        rating = int(rating)
    except (TypeError, ValueError):
        rating = 0
    rating = max(0, min(4, rating))
    sections, plain = normalize_ai_comment_sections(
        result.get("comment_sections"),
        legacy_comment=result.get("comment", ""),
    )
    return {
        "ai_score": rating,
        "ai_score_source": "resume",
        "ai_comment": plain,
        "ai_comment_sections": sections,
        "ai_strengths": result.get("strengths", []) or [],
        "ai_weaknesses": result.get("weaknesses", []) or [],
        "profile_checked": True,
    }


def generate_candidate_interview_questionnaire(
    resume_text,
    vacancy_profile,
    job_title,
    base_questionnaire,
    hr_comment,
    eval_comment,
    strengths,
    weaknesses,
    client,
    config,
    questionnaire_rules="",
):
    """Персональный опросник: образец вакансии + уточнения по резюме."""
    profile_block = trim_profile_for_eval(
        vacancy_profile,
        get_char_limit(config, "profile", 5000),
    )
    resume_limit = get_char_limit(config, "resume", 8000)
    eval_comment_limit = get_char_limit(config, "eval_comment", 1500)
    base_list = normalize_questionnaire_list(base_questionnaire or [])
    base_json = json.dumps(base_list, ensure_ascii=False, indent=2) if base_list else "[]"
    if len(base_json) > get_char_limit(config, "questionnaire", 4000):
        base_json = base_json[: get_char_limit(config, "questionnaire", 4000)]

    user_parts = [
        f"Должность: {job_title}",
        f"ПРОФИЛЬ:\n{profile_block}",
        f"РЕЗЮМЕ:\n{trim_text(resume_text, resume_limit)}",
        f"ТЕКУЩИЙ ОПРОСНИК ВАКАНСИИ (выбери ключевые вопросы, объединяй повторяющиеся):\n{base_json}",
    ]
    if (eval_comment or "").strip():
        user_parts.append(
            f"КОММЕНТАРИЙ ИИ ПО РЕЗЮМЕ:\n{trim_text(eval_comment, eval_comment_limit)}"
        )
    if strengths:
        user_parts.append("СИЛЬНЫЕ СТОРОНЫ:\n" + "\n".join(f"- {s}" for s in strengths[:10]))
    if weaknesses:
        user_parts.append("СЛАБЫЕ СТОРОНЫ / ПРОБЕЛЫ:\n" + "\n".join(f"- {w}" for w in weaknesses[:10]))
    hr_block = format_hr_comment_block(hr_comment, config)
    if hr_block:
        user_parts.append(hr_block.strip())
    user_parts.append(
        "Сформируй персональный опросник: 6–8 основных вопросов (макс. 10), "
        "обязательные блоки про мотивацию/уход/раздражители/рекомендации, "
        "ключевые вопросы из опросника вакансии без дублирования, "
        "плюс точечные вопросы по пробелам резюме."
    )

    system_content = CANDIDATE_QUESTIONNAIRE_SYSTEM
    if (questionnaire_rules or "").strip():
        system_content += f"\n\n{questionnaire_rules.strip()}"

    response = create_chat_completion(
        client,
        config,
        "questionnaire",
        messages=[
            {"role": "system", "content": system_content},
            {"role": "user", "content": "\n\n".join(user_parts)},
        ],
        temperature=0.3,
    )
    result = parse_ai_json_response(response.choices[0].message.content)
    raw = result.get("опросник", result if isinstance(result, list) else [])
    questionnaire = normalize_questionnaire_list(raw)
    if not questionnaire:
        raise ValueError("ИИ вернул пустой опросник")
    return questionnaire


def format_interview_eval_notes_block(notes, config=None):
    text = (notes or "").strip()
    if not text:
        return ""
    limit = get_char_limit(config, "interview_eval_notes", 2000) if config else 2000
    return (
        "\nУТОЧНЕНИЯ HR ДЛЯ ОЦЕНКИ ПО ИНТЕРВЬЮ (обязательно учти — снимают ложные стоп-факторы и задают контекст):\n"
        f"{text[:limit]}\n"
    )


def questionnaire_to_eval_prompt(questionnaire):
    """Текст опросника с оценками HR для оценки по интервью."""
    items = normalize_questionnaire_list(questionnaire)
    if not items:
        return ""
    lines = []
    for i, q in enumerate(items, 1):
        parts = [f"{i}. {q.get('вопрос', '')}"]
        if q.get("пример_ответа"):
            parts.append(f"   Желательный ответ: {q['пример_ответа']}")
        if q.get("в_резюме"):
            parts.append(f"   Уже в резюме: {q['в_резюме']}")
        resume_followups = q.get("уточнения_по_резюме") or []
        if resume_followups:
            parts.append(
                "   Уточнения по резюме: "
                + "; ".join(str(f) for f in resume_followups if str(f).strip())
            )
        rating = normalize_hr_rating(q.get("оценка_hr", q.get("оценка", "")))
        if rating:
            parts.append(f"   Оценка HR по ответу: {HR_RATING_LABELS.get(rating, rating)}")
        if q.get("ответ"):
            parts.append(f"   Заметка HR: {q['ответ']}")
        lines.append("\n".join(parts))
    return "\n\n".join(lines)


def questionnaire_to_prompt_text(questionnaire):
    eval_text = questionnaire_to_eval_prompt(questionnaire)
    if eval_text:
        return eval_text
    if not questionnaire:
        return ""
    if isinstance(questionnaire, str):
        return questionnaire
    return json.dumps(normalize_questionnaire_list(questionnaire), ensure_ascii=False, indent=2)


def _html_to_text(html):
    text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _extract_text_from_pdf_bytes(content):
    if not content or not content.lstrip().startswith(b"%PDF"):
        return ""
    reader = PyPDF2.PdfReader(BytesIO(content))
    return "\n".join(page.extract_text() or "" for page in reader.pages).strip()


def parse_yandex_link(url):
    """Разбирает ссылку yadisk:ROOT::/path или обычный public URL."""
    url = (url or "").strip()
    if url.startswith("yadisk:"):
        payload = url[7:]
        if "::" in payload:
            root, path = payload.split("::", 1)
            return root.strip(), (path or "").strip()
        return payload.strip(), ""
    return url, ""


def format_yandex_link(root_url, path=""):
    """Внутренний формат ссылки на файл/папку в опубликованной директории."""
    root = (root_url or "").strip()
    rel = (path or "").strip()
    if not root:
        return ""
    if not rel:
        return root
    if not rel.startswith("/"):
        rel = "/" + rel
    return f"yadisk:{root}::{rel}"


def yandex_public_view_url(root_url, path):
    """Ссылка на просмотр файла в веб-интерфейсе опубликованной папки (/d/)."""
    root = (root_url or "").strip().rstrip("/")
    rel = (path or "").strip()
    if not root:
        return ""
    if not rel:
        return root
    if not rel.startswith("/"):
        rel = "/" + rel
    segments = [quote(part, safe="") for part in rel.strip("/").split("/") if part]
    if not segments:
        return root
    return f"{root}/{'/'.join(segments)}"


def yandex_path_is_valid(public_key, path):
    """Проверяет, что файл/папка существует в опубликованной директории."""
    if not public_key:
        return False
    if not (path or "").strip():
        return True
    return get_yandex_public_meta(public_key, path=path) is not None


def yandex_link_for_display(url):
    """Ссылка для открытия в браузере/Telegram — просмотр в Диске, не скачивание."""
    url = (url or "").strip()
    if not url:
        return ""
    root, path = parse_yandex_link(url)
    if not root:
        return url
    if not path:
        return root
    if "/i/" in root:
        return root
    meta = get_yandex_public_meta(root, path=path)
    if meta:
        public_url = (meta.get("public_url") or "").strip()
        if public_url:
            return public_url
    if "/d/" in root:
        return yandex_public_view_url(root, path)
    return yandex_public_view_url(root, path)


def get_yandex_public_meta(url, *, path=None):
    public_key, parsed_path = parse_yandex_link(url)
    use_path = path if path is not None else parsed_path
    if not public_key:
        return None
    if not ("disk.yandex" in public_key or "yadi.sk" in public_key):
        return None
    params = {"public_key": public_key}
    if use_path:
        if not use_path.startswith("/"):
            use_path = "/" + use_path
        params["path"] = use_path
    try:
        response = requests.get(
            "https://cloud-api.yandex.net/v1/disk/public/resources",
            params=params,
            timeout=30,
        )
        if response.status_code == 200:
            return response.json()
    except requests.RequestException:
        pass
    return None


def list_yandex_public_folder(public_key, path="", *, limit=200):
    """Список файлов и папок в опубликованной директории."""
    meta = get_yandex_public_meta(public_key, path=path or "")
    if not meta:
        return []
    embedded = meta.get("_embedded") or {}
    return embedded.get("items") or []


def get_yandex_download_url(url, *, path=None):
    public_key, parsed_path = parse_yandex_link(url)
    use_path = path if path is not None else parsed_path
    meta = get_yandex_public_meta(public_key, path=use_path) if public_key else None
    if meta and meta.get("file"):
        return meta["file"]
    if not public_key:
        return None
    params = {"public_key": public_key}
    if use_path:
        if not use_path.startswith("/"):
            use_path = "/" + use_path
        params["path"] = use_path
    try:
        response = requests.get(
            "https://cloud-api.yandex.net/v1/disk/public/resources/download",
            params=params,
            timeout=30,
        )
        if response.status_code == 200:
            return response.json().get("href")
    except requests.RequestException:
        pass
    if "/i/" in public_key and not use_path:
        return public_key
    return None


def is_yandex_video_or_audio(meta):
    if not meta:
        return False
    media = (meta.get("media_type") or "").lower()
    if media in ("video", "audio"):
        return True
    mime = (meta.get("mime_type") or "").lower()
    name = (meta.get("name") or "").lower()
    if mime.startswith(("video/", "audio/")):
        return True
    return name.endswith((".mp4", ".webm", ".mov", ".avi", ".mkv", ".mp3", ".wav", ".ogg", ".m4a"))


def is_yandex_pdf(meta):
    if not meta:
        return False
    mime = (meta.get("mime_type") or "").lower()
    name = (meta.get("name") or "").lower()
    return mime == "application/pdf" or name.endswith(".pdf")


def fetch_resume_text_from_url(url, extract_text_from_pdf_url, transcribe_video_from_link=None):
    url = (url or "").strip()
    if not url:
        return "", "Пустая ссылка"

    if "disk.yandex" in url or "yadi.sk" in url:
        meta = get_yandex_public_meta(url)
        if meta and is_yandex_video_or_audio(meta):
            if not transcribe_video_from_link:
                label = meta.get("name") or "видео/аудио"
                return "", f"Ссылка ведёт на {label} — нужна расшифровка"
            text = transcribe_video_from_link(url) or ""
            if len(text) < 50:
                label = meta.get("name") or "видео"
                return "", f"Не удалось расшифровать {label}"
            return text, ""

        text = extract_text_from_pdf_url(url) or ""
        if len(text) >= 50:
            return text, ""

        if meta and not is_yandex_pdf(meta):
            label = meta.get("name") or meta.get("mime_type") or "файл"
            return "", f"Файл на Яндекс.Диске не PDF ({label})"
        return "", "Не удалось извлечь текст из PDF на Яндекс.Диске"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "ru-RU,ru;q=0.9",
    }
    try:
        response = requests.get(url, headers=headers, timeout=45, allow_redirects=True)
        if response.status_code != 200:
            return "", f"HTTP {response.status_code}"

        content_type = response.headers.get("Content-Type", "").lower()
        if "pdf" in content_type or url.lower().endswith(".pdf"):
            text = _extract_text_from_pdf_bytes(response.content)
            return (text, "") if len(text) >= 50 else ("", "PDF без текста")

        if "hh.ru" in url or "headhunter.ru" in url:
            text = _html_to_text(response.text)
            if len(text) < 200:
                return "", "hh.ru требует авторизации — загрузите PDF"
            return text, ""

        text = _html_to_text(response.text)
        return (text, "") if len(text) >= 100 else ("", "Мало текста по ссылке")
    except requests.RequestException as e:
        return "", str(e)
