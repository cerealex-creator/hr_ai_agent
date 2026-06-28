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
    BotCommand(
        command="meetings",
        description="Посмотреть назначенные собеседования",
    ),
    BotCommand(command="candidates", description="Карточки кандидатов вакансии"),
    BotCommand(command="pending", description="Кандидаты, ждут оценки"),
)


HELP_TEXT_HTML = (
    "<b>Справка по работе в Telegram</b>\n\n"
    "В групповом чате вакансии под карточкой кандидата есть кнопки статуса. "
    "«Встреча» и «Оффер» сохраняются сразу. "
    "«Отказ» и «Подумать» — только после комментария: бот попросит ответить на его сообщение. "
    "Без комментария статус не изменится.\n\n"
    "Отдельная кнопка «Комментарий» добавляет пояснение, не меняя статус. "
    "«Сменить статус» — если нужно исправить решение.\n\n"
    "Для «Встречи» после выбора статуса назначьте дату, время и формат (офис или удалённо). "
    "Встречу можно отменить кнопкой на карточке.\n\n"
    "Команды: /meetings — предстоящие встречи (подтверждены HR); "
    "/candidates — листать карточки вакансии; /pending — кто ждёт оценки. "
    "Сводка по кандидатам приходит по вторникам в 18:00 и по пятницам в 15:00 (Москва). "
    "В субботу и воскресенье автоматические напоминания не отправляются; "
    "накопленные за выходные уходят в понедельник в 10:00 (Москва).\n\n"
    "В личке с ботом: /start или /menu. Сначала напишите /start в группе отдела, "
    "чтобы бот запомнил ваш отдел."
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
