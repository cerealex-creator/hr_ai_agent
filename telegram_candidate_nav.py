"""Навигация по карточкам кандидатов вакансии в Telegram-чате."""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)

from client_actions import find_vacancies_by_chat_id, post_belongs_to_vacancy, post_kind
from telegram_chat_id import resolve_vacancy_chat_id
from models import is_visible_in_client_zone
from telegram_notify import _esc, chat_ids_equal, chat_id_variants, normalize_chat_id
from vacancy_store import get_status_meta, migrate_candidate


def _format_short_date(iso_str):
    raw = (iso_str or "").strip()[:10]
    if not raw:
        return "—"
    try:
        return datetime.strptime(raw, "%Y-%m-%d").strftime("%d.%m.%Y")
    except ValueError:
        return raw


def format_vacancy_nav_label(vacancy):
    """Подпись вакансии с периодом — отличает «Кладовщик» январь от «Кладовщик» июнь."""
    title = vacancy.get("title", "Вакансия")
    opened = _format_short_date(vacancy.get("created_at"))
    if vacancy.get("active", True):
        return f"{title} · с {opened}"
    closed = _format_short_date(vacancy.get("closed_at"))
    return f"{title} · {opened} — {closed} (архив)"


def find_vacancies_for_nav(chat_id, query=None):
    """
    Вакансии этого чата для навигатора.
    Без запроса — только активные. С запросом — по подстроке в названии;
    приоритет активным, иначе архив с тем же названием.
    """
    all_in_chat = find_vacancies_by_chat_id(chat_id, only_active=False)
    if not query:
        return [v for v in all_in_chat if v.get("active", True)]

    q = query.lower().strip()
    matched = [v for v in all_in_chat if q in (v.get("title") or "").lower()]
    if not matched:
        return []
    active = [v for v in matched if v.get("active", True)]
    return active if active else matched


def backfill_post_vacancy_ids(vacancy):
    """Проставляет vacancy_id старым записям telegram_posts кандидатов вакансии."""
    vac_id = vacancy.get("id")
    if vac_id is None:
        return
    for cand in vacancy.get("candidates", []):
        migrate_candidate(cand)
        for post in cand.get("telegram_posts", []):
            if post.get("vacancy_id") is None:
                post["vacancy_id"] = vac_id


def _filter_vacancy_card_posts(candidate, chat_id, vacancy_id, *, kind="primary"):
    return [
        p
        for p in candidate.get("telegram_posts", [])
        if chat_ids_equal(p.get("chat_id"), chat_id)
        and post_kind(p) == kind
        and post_belongs_to_vacancy(p, vacancy_id)
    ]


def get_vacancy_card_post(candidate, chat_id, vacancy_id, *, kind="primary"):
    posts = _filter_vacancy_card_posts(candidate, chat_id, vacancy_id, kind=kind)
    if not posts:
        return None
    return max(posts, key=lambda p: p.get("sent_at") or "")


def list_vacancy_card_posts(candidate, chat_id, vacancy_id, *, kind="primary"):
    """Все primary-карточки кандидата в чате, от новых к старым."""
    posts = _filter_vacancy_card_posts(candidate, chat_id, vacancy_id, kind=kind)
    posts.sort(key=lambda p: p.get("sent_at") or "", reverse=True)
    return posts


def _lookup_chat_ids(vacancy, runtime_chat_id=None):
    """Чаты для поиска карточек. В группе — только текущий чат, без legacy из posts."""
    chats = []
    seen = set()

    def _add(cid):
        if cid is None:
            return
        variants = chat_id_variants(cid)
        if not variants or variants & seen:
            return
        seen.update(variants)
        chats.append(cid)

    if runtime_chat_id is not None:
        _add(runtime_chat_id)
        _add(resolve_vacancy_chat_id(vacancy, runtime_chat_id))
        return chats

    _add(vacancy.get("chat_id"))
    _add(resolve_vacancy_chat_id(vacancy))
    backfill_post_vacancy_ids(vacancy)
    for cand in vacancy.get("candidates", []):
        migrate_candidate(cand)
        for post in cand.get("telegram_posts", []):
            _add(post.get("chat_id"))
    return chats


def collect_vacancy_navigator_items(vacancy, runtime_chat_id=None):
    """Кандидаты вакансии с карточкой primary в текущем или привязанном чате."""
    backfill_post_vacancy_ids(vacancy)
    vac_id = vacancy.get("id")
    if vac_id is None:
        return []

    lookup_chats = _lookup_chat_ids(vacancy, runtime_chat_id)
    if not lookup_chats:
        return []

    items = []
    seen = set()
    for lookup_chat in lookup_chats:
        for cand in vacancy.get("candidates", []):
            migrate_candidate(cand)
            cand_id = cand.get("id")
            if cand_id in seen:
                continue
            post = get_vacancy_card_post(cand, lookup_chat, vac_id, kind="primary")
            if post:
                seen.add(cand_id)
                items.append({"candidate": cand, "post": post})

    items.sort(key=lambda x: x["post"].get("sent_at") or "")
    return items


async def _send_pointer_reply(bot, runtime_chat_id, card_id, name, track_fn):
    from telegram_nav_session import POINTER_TTL_SEC

    pointer = await bot.send_message(
        runtime_chat_id,
        f"👆 <b>{name}</b> — карточка кандидата",
        parse_mode="HTML",
        reply_to_message_id=int(card_id),
    )
    await track_fn(pointer.message_id)
    return f"Карточка отмечена ↑ (исчезнет через {POINTER_TTL_SEC} с)"


async def _try_pointer_for_message(
    bot,
    runtime_chat_id,
    post_chat,
    runtime_chat,
    card_id,
    name,
    track_fn,
):
    """Ответ на карточку: reply в том же чате или copy + reply."""
    if chat_ids_equal(post_chat, runtime_chat):
        try:
            return await _send_pointer_reply(
                bot, runtime_chat_id, card_id, name, track_fn
            )
        except Exception as exc:
            logger.warning(
                "reply_to карточки не удался chat=%s msg=%s: %s",
                runtime_chat_id,
                card_id,
                exc,
            )
            try:
                copied = await bot.copy_message(
                    chat_id=runtime_chat_id,
                    from_chat_id=post_chat,
                    message_id=int(card_id),
                )
                return await _send_pointer_reply(
                    bot, runtime_chat_id, copied.message_id, name, track_fn
                )
            except Exception as exc2:
                logger.warning(
                    "copy карточки в том же чате не удался msg=%s: %s",
                    card_id,
                    exc2,
                )
                return None

    try:
        copied = await bot.copy_message(
            chat_id=runtime_chat_id,
            from_chat_id=post_chat,
            message_id=int(card_id),
        )
        return await _send_pointer_reply(
            bot, runtime_chat_id, copied.message_id, name, track_fn
        )
    except Exception as exc:
        logger.warning(
            "copy карточки из другого чата не удался from=%s msg=%s: %s",
            post_chat,
            card_id,
            exc,
        )
        return None


async def send_candidate_card_pointer(bot, runtime_chat_id, user_id, item, *, vacancy=None):
    """
    Показывает карточку кандидата в текущем чате ответом на сообщение.
    Перебирает известные message_id (от новых к старым).
    """
    from telegram_nav_session import schedule_pointer_cleanup, track_pointer

    cand = item["candidate"]
    name = _esc(cand.get("name", "Кандидат"))
    runtime_chat = normalize_chat_id(runtime_chat_id)
    vac_id = (vacancy or {}).get("id")

    posts_to_try = list_vacancy_card_posts(cand, runtime_chat_id, vac_id)
    if not posts_to_try:
        posts_to_try = [item["post"]]

    async def _track_pointer(pointer_id):
        track_pointer(runtime_chat_id, user_id, pointer_id)
        import asyncio

        asyncio.create_task(
            schedule_pointer_cleanup(bot, runtime_chat_id, user_id, pointer_id)
        )

    for post in posts_to_try:
        card_id = post.get("message_id")
        if card_id is None:
            continue
        post_chat = normalize_chat_id(post.get("chat_id"))
        feedback = await _try_pointer_for_message(
            bot,
            runtime_chat_id,
            post_chat,
            runtime_chat,
            card_id,
            name,
            _track_pointer,
        )
        if feedback:
            if vacancy:
                from telegram_client import anchor_candidate_card_message

                anchor_candidate_card_message(
                    vacancy, cand, runtime_chat_id, int(card_id)
                )
            return True, feedback

    return (
        False,
        "Карточка не найдена в чате (сообщение удалено или устарела привязка). "
        "Нажмите любую кнопку на актуальной карточке в ленте или отправьте кандидата "
        "заново из HR.",
    )


def format_navigator_html(vacancy, item, index, total):
    cand = item["candidate"]
    meta = get_status_meta(cand.get("client_status", "wait"))
    name = _esc(cand.get("name", "Без имени"))
    vac_label = _esc(format_vacancy_nav_label(vacancy))

    lines = [
        f"<b>📋 {vac_label}</b>",
        f"Кандидат <b>{index + 1}</b> из <b>{total}</b>",
        "",
        f"👤 <b>{name}</b>",
        f"Статус заказчика: {meta['icon']} {meta['label']}",
    ]
    if is_visible_in_client_zone(cand):
        sent = (item["post"].get("sent_at") or "")[:10]
        if sent:
            lines.append(f"📨 Карточка в чате: {_format_short_date(sent)}")
    return "\n".join(lines)


def build_navigator_keyboard(vacancy, index, total):
    """Клавиатура ◀ N/M ▶ и переход к карточке (callback, не URL)."""
    vac_id = vacancy.get("id")
    prev_i = (index - 1) % total
    next_i = (index + 1) % total

    rows = [
        [
            {"text": "◀", "callback_data": f"cn:{vac_id}:{prev_i}"},
            {"text": f"{index + 1} / {total}", "callback_data": f"cn:{vac_id}:noop:{index}"},
            {"text": "▶", "callback_data": f"cn:{vac_id}:{next_i}"},
        ],
        [{"text": "🔗 Перейти к карточке", "callback_data": f"cg:{vac_id}:{index}"}],
    ]

    chat_vacancies = find_vacancies_for_nav(
        resolve_vacancy_chat_id(vacancy)
    )
    active_count = sum(1 for v in chat_vacancies if v.get("active", True))
    if active_count > 1 or len(chat_vacancies) > 1:
        rows.append([{"text": "📋 Другая вакансия", "callback_data": "cn:pick:0"}])

    rows.append([{"text": "✖️ Закончить", "callback_data": "cf:0"}])
    return {"inline_keyboard": rows}


def vacancy_picker_keyboard(vacancies):
    rows = []
    for vac in vacancies:
        label = format_vacancy_nav_label(vac)
        if len(label) > 60:
            label = label[:57] + "…"
        rows.append([{"text": label, "callback_data": f"cv:{vac['id']}"}])
    rows.append([{"text": "✖️ Закончить", "callback_data": "cf:0"}])
    return {"inline_keyboard": rows}
