"""ИИ: извлечение данных из резюме и оценка на первичной стадии."""

import json
import re
from io import BytesIO

import requests
import PyPDF2

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
Если передан КОММЕНТАРИЙ HR — обязательно учти его: это живые замечания рекрутера после контакта с кандидатом; согласуй оценку с ними и отрази в comment."""

QUESTIONNAIRE_ITEM_SCHEMA = """{
  "вопрос": "основной вопрос в разговорной форме",
  "уточняющие_вопросы": ["уточнение 1"],
  "проверяет_требование": "какой пункт профиля проверяем",
  "категория": "hard_skills | soft_skills | experience",
  "пример_ответа": "реалистичный ответ сильного кандидата"
}"""

CANDIDATE_QUESTIONNAIRE_SYSTEM = (
    """Ты — HR-директор. Сформируй персональный опросник для первичного собеседования КОНКРЕТНОГО кандидата.

Правила:
1. Если передан ТЕКУЩИЙ ОПРОСНИК вакансии — включи ВСЕ его основные вопросы (сохрани проверяет_требование и категория; пример_ответа можно уточнить под должность).
2. Добавь 2–4 ДОПОЛНИТЕЛЬНЫХ основных вопроса по пробелам в резюме и слабым сторонам из оценки ИИ — с уточняющими_вопросы и пример_ответа.
3. Если текущий опросник пуст — сформируй 6–8 вопросов по профилю должности, персонализируя под резюме.
4. Стиль беседы: «Был ли у Вас опыт ...? Расскажите на примере», не допрос.
5. К каждому основному вопросу — 1–3 уточняющих вопроса.
6. Опросник должен позволить по расшифровке интервью объективно оценить каждое требование профиля.

Верни ТОЛЬКО JSON:
{"опросник": ["""
    + QUESTIONNAIRE_ITEM_SCHEMA
    + """]}"""
)


def parse_ai_json_response(content):
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0]
    elif "```" in content:
        content = content.split("```")[1].split("```")[0]
    return json.loads(content.strip())


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
    response = client.chat.completions.create(
        model=config["model"]["name"],
        messages=[
            {"role": "system", "content": RESUME_EXTRACT_SYSTEM},
            {"role": "user", "content": f"Текст резюме:\n{resume_text[:12000]}"},
        ],
        temperature=0.1,
        max_tokens=800,
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


def format_hr_comment_block(hr_comment):
    text = (hr_comment or "").strip()
    if not text:
        return ""
    return (
        "\nКОММЕНТАРИЙ HR (обязательно учти при оценке — замечания рекрутера после контакта с кандидатом):\n"
        f"{text[:4000]}\n"
    )


def evaluate_resume_with_ai(
    resume_text, vacancy_profile, job_title, client, config, hr_comment=""
):
    profile_block = vacancy_profile or "Профиль не задан"
    hr_block = format_hr_comment_block(hr_comment)
    response = client.chat.completions.create(
        model=config["model"]["name"],
        messages=[
            {"role": "system", "content": RESUME_EVAL_SYSTEM},
            {
                "role": "user",
                "content": (
                    f"Должность: {job_title}\n\nПРОФИЛЬ:\n{profile_block[:8000]}\n\n"
                    f"РЕЗЮМЕ:\n{resume_text[:12000]}"
                    f"{hr_block}"
                ),
            },
        ],
        temperature=0.3,
        max_tokens=config["model"]["max_tokens"],
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
):
    """Персональный опросник: образец вакансии + уточнения по резюме."""
    profile_block = vacancy_profile or "Профиль не задан"
    base_list = normalize_questionnaire_list(base_questionnaire or [])
    base_json = json.dumps(base_list, ensure_ascii=False, indent=2) if base_list else "[]"

    user_parts = [
        f"Должность: {job_title}",
        f"ПРОФИЛЬ:\n{profile_block[:8000]}",
        f"РЕЗЮМЕ:\n{resume_text[:12000]}",
        f"ТЕКУЩИЙ ОПРОСНИК ВАКАНСИИ (образец — обязательная основа):\n{base_json}",
    ]
    if (eval_comment or "").strip():
        user_parts.append(f"КОММЕНТАРИЙ ИИ ПО РЕЗЮМЕ:\n{eval_comment[:2000]}")
    if strengths:
        user_parts.append("СИЛЬНЫЕ СТОРОНЫ:\n" + "\n".join(f"- {s}" for s in strengths[:10]))
    if weaknesses:
        user_parts.append("СЛАБЫЕ СТОРОНЫ / ПРОБЕЛЫ:\n" + "\n".join(f"- {w}" for w in weaknesses[:10]))
    hr_block = format_hr_comment_block(hr_comment)
    if hr_block:
        user_parts.append(hr_block.strip())
    user_parts.append(
        "Сформируй полный опросник для собеседования этого кандидата: все вопросы из текущего опросника вакансии "
        "+ дополнительные уточняющие по резюме (с примерами желательных ответов)."
    )

    response = client.chat.completions.create(
        model=config["model"]["name"],
        messages=[
            {"role": "system", "content": CANDIDATE_QUESTIONNAIRE_SYSTEM},
            {"role": "user", "content": "\n\n".join(user_parts)},
        ],
        temperature=0.3,
        max_tokens=config["model"]["max_tokens"],
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
    reader = PyPDF2.PdfReader(BytesIO(content))
    return "\n".join(page.extract_text() or "" for page in reader.pages).strip()


def fetch_resume_text_from_url(url, extract_text_from_pdf_url):
    url = (url or "").strip()
    if not url:
        return "", "Пустая ссылка"

    if "disk.yandex" in url or "yadi.sk" in url:
        text = extract_text_from_pdf_url(url) or ""
        if len(text) < 50:
            return "", "Не удалось извлечь текст из PDF на Яндекс.Диске"
        return text, ""

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
