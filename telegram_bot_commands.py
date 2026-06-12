"""Регистрация команд бота в меню Telegram (кнопка «Меню» и список после /)."""

import logging

from aiogram import Bot
from aiogram.types import (
    BotCommand,
    BotCommandScopeAllGroupChats,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeDefault,
)

logger = logging.getLogger(__name__)

PRIVATE_COMMANDS = (
    BotCommand(command="start", description="Главное меню"),
    BotCommand(command="menu", description="Главное меню"),
)

GROUP_COMMANDS = (
    BotCommand(command="candidates", description="Карточки кандидатов вакансии"),
    BotCommand(command="pending", description="Кандидаты, ждут оценки"),
)


HELP_TEXT_HTML = (
    "📖 <b>Справка HR-помогатор</b>\n\n"
    "<b>В групповом чате:</b>\n"
    "• /candidates — карточки вакансии (◀ ▶, «Перейти к карточке», «Закончить»)\n"
    "• /pending — кто ждёт оценки (фильтр по вакансии)\n"
    "• сводка по кандидатам — автоматически вт 18:00 и пт 15:00\n"
    "• под карточкой кандидата — кнопки статуса\n"
    "• Отказ/Подумать — с комментарием; Встреча/Оффер — без\n"
    "• 💬 или ответ на карточку — отдельный комментарий\n\n"
    "<b>В личном чате с ботом:</b>\n"
    "• /start или /menu — вакансии и кандидаты\n"
    "• сначала /start в группе отдела, затем /start в личке\n\n"
    "Команды доступны через кнопку <b>Меню</b> (☰) слева от поля ввода."
)


async def register_bot_commands(bot: Bot) -> None:
    """Публикует команды в меню Telegram (мобильный и десктоп)."""
    await bot.set_my_commands(list(PRIVATE_COMMANDS), scope=BotCommandScopeDefault())
    await bot.set_my_commands(
        list(PRIVATE_COMMANDS),
        scope=BotCommandScopeAllPrivateChats(),
    )
    await bot.set_my_commands(
        list(GROUP_COMMANDS),
        scope=BotCommandScopeAllGroupChats(),
    )
    logger.info(
        "Команды бота зарегистрированы: личка=%s, группы=%s",
        [c.command for c in PRIVATE_COMMANDS],
        [c.command for c in GROUP_COMMANDS],
    )
