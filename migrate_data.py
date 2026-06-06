import json
import os

VACANCIES_FILE = "data/vacancies_db.json"

def migrate():
    if not os.path.exists(VACANCIES_FILE):
        print(f"Файл {VACANCIES_FILE} не найден")
        return
    
    with open(VACANCIES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    vacancies = data.get("vacancies", [])
    if not vacancies:
        print("Нет данных")
        return
    
    # ---- 1. Удаляем дубликаты вакансий по названию + chat_id (оставляем первую) ----
    unique_vacancies = []
    seen = set()
    for v in vacancies:
        key = (v.get("title", ""), v.get("chat_id", ""))
        if key not in seen:
            seen.add(key)
            unique_vacancies.append(v)
        else:
            print(f"Удалён дубликат вакансии: {v.get('title')} (id={v.get('id')})")
    vacancies = unique_vacancies
    
    # ---- 2. Перенумеровываем id вакансий последовательно ----
    old_to_new_id = {}
    new_vacancies = []
    for idx, v in enumerate(vacancies, start=1):
        old_id = v.get("id")
        new_id = idx
        old_to_new_id[old_id] = new_id
        v["id"] = new_id
        new_vacancies.append(v)
    print(f"Перенумеровано {len(new_vacancies)} вакансий")
    
    # ---- 3. Добавляем недостающие поля в вакансии ----
    for v in new_vacancies:
        if "client_id" not in v:
            # По умолчанию – админ (0), или можно попробовать определить по chat_id? Но пусть 0.
            v["client_id"] = 0
        if "active" not in v:
            v["active"] = True
        if "documents" not in v:
            v["documents"] = {
                "profile": "",
                "vacancy_text": "",
                "questions": "",
                "keywords": "",
                "notes": ""
            }
    
    # ---- 4. Обрабатываем кандидатов: обновляем vacancy_id, добавляем поля, удаляем дубликаты ----
    for v in new_vacancies:
        candidates = v.get("candidates", [])
        # Исправляем vacancy_id у каждого кандидата
        for c in candidates:
            old_vacancy_id = c.get("vacancy_id")
            if old_vacancy_id in old_to_new_id:
                c["vacancy_id"] = old_to_new_id[old_vacancy_id]
            else:
                # Если нет vacancy_id или он не соответствует, ставим id текущей вакансии
                c["vacancy_id"] = v["id"]
            # Добавляем недостающие поля со значениями по умолчанию
            if "hr_comment" not in c:
                c["hr_comment"] = ""
            if "task_link" not in c:
                c["task_link"] = ""
            if "client_status" not in c:
                c["client_status"] = "wait"
            if "client_comment" not in c:
                c["client_comment"] = ""
            if "office_interview_date" not in c:
                c["office_interview_date"] = ""
            if "ai_score" not in c:
                c["ai_score"] = None
            if "ai_comment" not in c:
                c["ai_comment"] = ""
            if "ai_strengths" not in c:
                c["ai_strengths"] = []
            if "ai_weaknesses" not in c:
                c["ai_weaknesses"] = []
            if "transcript" not in c:
                c["transcript"] = ""
        
        # Удаляем дубликаты кандидатов внутри одной вакансии (по имени + resume_link)
        unique_candidates = []
        seen_cand = set()
        for c in candidates:
            key = (c.get("name", ""), c.get("resume_link", ""))
            if key not in seen_cand:
                seen_cand.add(key)
                unique_candidates.append(c)
            else:
                print(f"Удалён дубликат кандидата: {c.get('name')} в вакансии {v['title']}")
        v["candidates"] = unique_candidates
    
    # ---- 5. Сохраняем исправленные данные ----
    data["vacancies"] = new_vacancies
    with open(VACANCIES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print("Миграция завершена успешно!")
    print(f"Всего вакансий: {len(new_vacancies)}")

if __name__ == "__main__":
    migrate()