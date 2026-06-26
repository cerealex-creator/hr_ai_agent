"""ИИ: извлечение данных из резюме и оценка на первичной стадии."""

import json
import re
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

RESUME_EVAL_SYSTEM = """Ты — опытный HR-директор. Оцени соответствие резюме профилю должности на этапе холодного отбора.
Шкала rating: 0–4 (целое число).
Верни ТОЛЬКО JSON:
{
  "rating": 3,
  "comment": "Краткий комментарий 2–4 предложения",
  "strengths": ["..."],
  "weaknesses": ["..."]
}

Дополнительно проанализируй риски (отрази в weaknesses и/или comment):
- Частая смена работы, неясные или противоречивые причины ухода, переход с фриланса/самозанятости без логики в резюме.
- Длительные пробелы в опыте без пояснения — отметь необходимость выяснить причину на интервью.
- Признаки излишней требовательности (только идеальные условия, много жёстких «не готов» без гибкости).
На этапе резюме лояльность, адекватность и управляемость оцени предварительно по косвенным признакам; явно укажи в comment, что нужно проверить на интервью (мотивация, причины ухода, обратная связь от работодателей).

Если передан КОММЕНТАРИЙ HR — обязательно учти его: это живые замечания рекрутера после контакта с кандидатом; согласуй оценку с ними и отрази в comment."""

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


def extract_data_from_resume(resume_text, client, config):
    if not resume_text or not resume_text.strip():
        raise ValueError("Пустой текст резюме")
    resume_limit = get_char_limit(config, "resume", 8000)
    response = create_chat_completion(
        client,
        config,
        "extract",
        messages=[
            {"role": "system", "content": RESUME_EXTRACT_SYSTEM},
            {"role": "user", "content": f"Текст резюме:\n{trim_text(resume_text, resume_limit)}"},
        ],
        temperature=0.1,
    )
    data = parse_ai_json_response(response.choices[0].message.content)
    return {
        "name": data.get("full_name") or "Нет информации",
        "phone": format_phone(data.get("phone")),
        "age": data.get("age") if str(data.get("age", "")).strip() else "",
        "city": data.get("city") if str(data.get("city", "")).strip() else "",
        "metro": data.get("metro") if str(data.get("metro", "")).strip() else "",
        "age_location": format_age_location(data.get("age"), data.get("metro"), data.get("city")),
        "salary_expected": format_salary(data.get("salary")),
    }


def normalize_questionnaire_list(items):
    if not isinstance(items, list):
        return []
    result = []
    for q in items:
        if isinstance(q, str):
            result.append({"вопрос": q, "уточняющие_вопросы": [], "проверяет_требование": "", "категория": "", "пример_ответа": ""})
        elif isinstance(q, dict):
            followups = q.get("уточняющие_вопросы", q.get("followups", []))
            if isinstance(followups, str):
                followups = [followups] if followups.strip() else []
            result.append({
                "вопрос": q.get("вопрос", q.get("question", "")),
                "уточняющие_вопросы": [str(f) for f in followups] if isinstance(followups, list) else [],
                "проверяет_требование": q.get("проверяет_требование", q.get("requirement", "")),
                "категория": q.get("категория", q.get("category", "")),
                "пример_ответа": q.get("пример_ответа", q.get("example", "")),
            })
    return [q for q in result if (q.get("вопрос") or "").strip()]


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
    )
    result = parse_ai_json_response(response.choices[0].message.content)
    rating = result.get("rating", 0)
    try:
        rating = int(rating)
    except (TypeError, ValueError):
        rating = 0
    rating = max(0, min(4, rating))
    return {
        "ai_score": rating,
        "ai_score_source": "resume",
        "ai_comment": result.get("comment", ""),
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


def questionnaire_to_prompt_text(questionnaire):
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
    if "/i/" in public_key:
        return public_key.replace("/i/", "/d/")
    return public_key


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
