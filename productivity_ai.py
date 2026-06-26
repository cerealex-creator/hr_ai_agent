"""ИИ-анализ продуктивности HR за период."""

import json

from ai_helpers import create_chat_completion, trim_text
from period_productivity import METRIC_LABELS, format_period_label


def build_productivity_analysis_payload(
    *,
    period_type,
    year,
    index,
    current_metrics,
    previous_metrics,
    baseline_months,
    baseline_averages,
    comparison_rows,
    context_extras,
    dept_breakdown,
    vacancies_in_work_titles,
):
    period_label = format_period_label(period_type, year, index)
    prev_label = format_period_label(
        period_type,
        previous_metrics.period_start.year,
        _index_from_bounds(period_type, previous_metrics.period_start),
    )

    metrics_block = []
    for row in comparison_rows:
        metrics_block.append({
            "показатель": row["label"],
            "текущий_период": row["current"],
            "предыдущий_период": row["previous"],
            "изменение_к_пред": row["delta_prev"],
            "среднее_за_месяцы": round(row["average"], 2) if row["average"] is not None else None,
            "изменение_к_среднему": round(row["delta_avg"], 2) if row["delta_avg"] is not None else None,
        })

    payload = {
        "текущий_период": period_label,
        "предыдущий_период": prev_label,
        "база_для_среднего": f"{baseline_months} календарных мес." if baseline_months else "мало данных",
        "показатели": metrics_block,
        "закрыто_успешно_детализация": {
            "всего": current_metrics.vacancies_closed_success,
            "начатых_ранее_периода": current_metrics.vacancies_closed_success_started_before,
            "начатых_и_закрытых_в_периоде": current_metrics.vacancies_closed_success_started_in_period,
            "строки": current_metrics.vacancies_closed_success_details,
        },
        "взято_в_работу_детализация": current_metrics.vacancies_started_details,
        "приглашены_детализация": current_metrics.invited_work_details,
        "закрыто_не_успешно_детализация": current_metrics.vacancies_closed_not_success_details,
        "вакансий_в_работе_за_период": current_metrics.vacancies_in_work,
        "вакансии_в_работе": vacancies_in_work_titles,
        "доп_факторы": context_extras,
        "по_подразделениям": dept_breakdown,
        "пояснения_к_метрикам": {
            METRIC_LABELS["vacancies_started"]: "вакансии, созданные (взяты в работу) в периоде",
            METRIC_LABELS["selected_candidates"]: "все кандидаты, добавленные в приложение за период",
            METRIC_LABELS["primary_interviews"]: (
                "первый переход с этапа «Назначено собеседование» на следующий рабочий этап "
                "(не отказ и не откат назад)"
            ),
            METRIC_LABELS["client_review"]: "первый переход на «На оценке у заказчика»",
            METRIC_LABELS["client_approved"]: "первое одобрение заказчиком (статус Встреча или Оффер)",
            METRIC_LABELS["invited_work"]: (
                "оффер, стажировка или прямой выход на работу без оффера/стажировки"
            ),
            METRIC_LABELS["vacancies_closed_success"]: "закрытие после выхода на работу/стажировку",
            METRIC_LABELS["vacancies_closed_client"]: "закрытие по инициативе заказчика",
        },
    }
    return payload


def _index_from_bounds(period_type, start_date):
    if period_type == "month":
        return start_date.month
    if period_type == "quarter":
        return (start_date.month - 1) // 3 + 1
    return 1 if start_date.month <= 6 else 2


def analyze_productivity_with_ai(client, config, payload):
    context_json = trim_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        limit=12000,
    )
    system_prompt = """Ты — HR-аналитик для рекрутера.
Анализируй продуктивность за период по фактам из JSON.
Не выдумывай цифры — опирайся только на переданные данные.
Если истории мало — честно скажи, что выводы предварительные.
Пиши по-русски, структурированно, без markdown-таблиц.
Главный KPI — закрытые вакансии (успешно); связывай остальные показатели с конверсией к этому результату."""

    user_prompt = f"""Данные продуктивности HR:

{context_json}

Сформируй отчёт из разделов:
1. Краткий итог периода (3–5 предложений).
2. Сравнение с предыдущим периодом — что выросло/упало и почему это важно.
3. Сравнение со средним за доступные месяцы — есть ли устойчивый тренд или всплеск.
4. Узкие места воронки (где теряется конверсия между этапами).
5. Конкретные рекомендации на следующий период (3–6 пунктов, приоритет по влиянию на закрытие вакансий).
6. На что обратить внимание по вакансиям в работе и подразделениям (если данные есть).

Будь конкретным: ссылайся на цифры из JSON."""

    response = create_chat_completion(
        client,
        config,
        task="stats_analysis",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=2500,
        temperature=0.4,
    )
    return (response.choices[0].message.content or "").strip()
