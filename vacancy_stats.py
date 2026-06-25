"""Подзона «Итоги» — статистика по вакансии."""

import streamlit as st

from models import (
    HR_STAGES,
    OFFER_STAGE,
    CLIENT_STATUS_LABELS,
    stage_counts,
    reached_hr_stage,
    reached_client_status,
    is_visible_in_client_zone,
)
from funnel_metrics import (
    candidate_vacancy_entries,
    compute_funnel_metrics,
)
from warranty import (
    is_warranty_active,
    migrate_vacancy_warranty,
    vacancy_days_in_work,
)


def _ever_reached_offer(candidate):
    return reached_hr_stage(candidate, OFFER_STAGE) or reached_client_status(
        candidate, "offer"
    )


def _render_vacancy_stats_header(vacancy):
    migrate_vacancy_warranty(vacancy)
    days, since = vacancy_days_in_work(vacancy)
    is_active = vacancy.get("active", True)
    work_verb = "Находится в работе" if is_active else "Находилась в работе"
    status_label = "Активная" if is_active else "В архиве"
    warranty_label = "На гарантии" if is_warranty_active(vacancy) else "Не на гарантии"

    parts = [f"**{status_label}**", f"**{warranty_label}**"]
    if days is not None:
        parts.insert(0, f"{work_verb} **{days}** дн. (с {since})")
    st.markdown(" · ".join(parts))


def render_vacancy_stats(vacancy):
    st.subheader("📊 Статистика")
    _render_vacancy_stats_header(vacancy)

    candidates = vacancy.get("candidates", [])
    if not candidates:
        st.info("Нет кандидатов для статистики.")
        return

    counts = stage_counts(candidates)
    st.markdown("**Воронка HR (сейчас на этапе)**")
    cols = st.columns(min(len(HR_STAGES), 5))
    for i, (code, label) in enumerate(HR_STAGES.items()):
        with cols[i % 5]:
            st.metric(label[:18], counts.get(code, 0))

    entries = candidate_vacancy_entries(candidates, vacancy)
    funnel = compute_funnel_metrics(entries)

    st.markdown("**Сводка по этапам (за всё время)**")
    st.write(f"- Всего отобрано для рассмотрения: **{funnel['total_selected']}**")
    st.write(f"- Первый контакт (сообщение): **{funnel['primary_contact']}**")
    st.caption(
        "Первый контакт: явный этап «Первичный контакт», "
        "либо «Назначено собеседование» (в т.ч. если договорились до внесения в приложение)."
    )
    st.write(f"- Не общался/пропали со связи: **{funnel['no_contact']}**")
    st.caption(
        "«Не общался» — только по истории: первичный контакт → отказ "
        "или остался на первичном контакте при закрытии вакансии."
    )
    st.write(f"- Прошли первичное собеседование: **{funnel['interview_done']}**")
    st.write(f"- Внесены в список на рассмотрение: **{funnel['client_review']}**")
    st.write(f"- Выполнили задание/тест: **{funnel['test_task']}**")
    st.write(f"- Получили отказ от меня: **{funnel['rejected_hr']}**")
    st.write(f"- Получили отказ от заказчика: **{funnel['rejected_client']}**")
    st.write(f"- Отказались сами: **{funnel['rejected_candidate']}**")
    st.caption(
        "Первичное собеседование ≥ список на рассмотрение ≥ выполнили задание. "
        "Считается по истории смен этапов."
    )

    ever_client_review = funnel["client_review"]
    ever_offer = sum(1 for c in candidates if _ever_reached_offer(c))
    current_offer = sum(1 for c in candidates if c.get("hr_stage") == OFFER_STAGE)

    st.markdown("**Конверсия (за всё время по вакансии)**")
    if ever_client_review:
        pct = ever_offer / ever_client_review * 100
        st.write(
            f"- На оценке у заказчика → получили оффер: "
            f"**{ever_offer}/{ever_client_review}** ({pct:.0f}%)"
        )
        st.caption(f"Сейчас на этапе «Оффер»: **{current_offer}**.")
    else:
        st.caption("Пока никого не отправляли на оценку заказчику.")

    visible = [c for c in candidates if is_visible_in_client_zone(c)]
    now_wait = sum(
        1 for c in visible if c.get("client_status", "wait") == "wait"
    )

    st.markdown("**Статусы заказчика**")
    st.caption(
        f"Всего отправлялись на оценку заказчику: **{ever_client_review}**. "
        f"Сейчас ждут выбора статуса: **{now_wait}**."
    )
    if visible:
        client_counts = {}
        for c in visible:
            s = c.get("client_status", "wait")
            client_counts[s] = client_counts.get(s, 0) + 1
        st.markdown("*Сейчас у кандидатов на оценке у заказчика:*")
        for key, cnt in sorted(
            client_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        ):
            st.write(f"- {CLIENT_STATUS_LABELS.get(key, key)}: **{cnt}**")
    else:
        st.caption("Сейчас нет кандидатов на оценке у заказчика.")

    st.markdown("**Итог по вакансии**")
    summary = vacancy.get("vacancy_summary", "")
    new_summary = st.text_area(
        "Общий итог HR", value=summary, height=120, key=f"vac_summary_{vacancy['id']}"
    )
    if st.button("💾 Сохранить итог", key=f"save_summary_{vacancy['id']}"):
        vacancy["vacancy_summary"] = new_summary
        return True
    return False
