import asyncio
import json
import os
import logging
from aiogram import Bot, Dispatcher, F, types
from interview_schedule import process_interview_reminders
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from dotenv import load_dotenv
from telegram_notify import get_hr_user_id, normalize_chat_id
from telegram_bot_handlers import register_client_zone_handlers, try_handle_pending_comment

load_dotenv()

# ---------- Конфигурация ----------
def _admin_user_id():
    return get_hr_user_id() or 814639854


SECRET_GROUP_TOKEN = os.getenv("TELEGRAM_GROUP_LINK_TOKEN", "your_secret_token_here")

# ---------- Работа с данными ----------
VACANCIES_FILE = "data/vacancies_db.json"
CHATS_FILE = "data/chats_db.json"

def load_vacancies():
    from vacancy_store import load_vacancies_list
    return load_vacancies_list()

def save_vacancies(vacancies):
    from vacancy_store import save_vacancies_list
    save_vacancies_list(vacancies)

def load_chats():
    if not os.path.exists(CHATS_FILE):
        return []
    with open(CHATS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def get_department_id_by_chat_id(chat_id):
    chats = load_chats()
    for c in chats:
        if str(c["id"]) == str(chat_id):
            return c.get("department_id")
    return None

def get_vacancies_for_department(dept_id, only_active=True):
    vacancies = load_vacancies()
    result = []
    for v in vacancies:
        if v.get("client_id") == dept_id:
            if only_active and not v.get("active", True):
                continue
            result.append(v)
    return result

# ---------- Бот ----------
TOKEN = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
if not TOKEN:
    raise ValueError("Не задан TELEGRAM_BOT_TOKEN в окружении")

bot = Bot(token=TOKEN)
dp = Dispatcher()
logger = logging.getLogger(__name__)

register_client_zone_handlers(dp)

# Временное хранилище для привязки пользователя к отделу (после глубокой ссылки)
user_dept = {}

# ---------- Команды /id и /chatid ----------
@dp.message(Command("id"))
async def cmd_id(message: types.Message):
    lines = [f"Ваш user_id: <code>{message.from_user.id}</code>"]
    if message.chat.type != "private":
        lines.append(f"ID этого чата: <code>{message.chat.id}</code>")
    await message.answer("\n".join(lines), parse_mode="HTML")


@dp.message(Command("chatid"))
async def cmd_chatid(message: types.Message):
    await message.answer(
        f"ID чата: <code>{message.chat.id}</code>\n"
        f"Тип: {message.chat.type}",
        parse_mode="HTML",
    )

# ---------- Команда /start (в личке или группе) ----------
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    deep_link_param = message.text.replace("/start", "").strip()

    # Если это личный чат и нет параметра – просто приветствие
    if message.chat.type == "private" and not deep_link_param:
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(text="📋 Вакансии", callback_data="menu_vacancies"))
        builder.add(InlineKeyboardButton(text="📂 Архив", callback_data="menu_archive"))
        builder.add(InlineKeyboardButton(text="❓ Помощь", callback_data="menu_help"))
        await message.answer("👋 Добро пожаловать! Выберите действие:", reply_markup=builder.as_markup())
        return

    # Если команда пришла из группы – определяем отдел и привязываем пользователя
    if message.chat.type in ["group", "supergroup"]:
        dept_id = get_department_id_by_chat_id(chat_id)
        if not dept_id:
            await message.answer("Этот чат не привязан к отделу. Обратитесь к администратору.")
            return
        # Запоминаем привязку user_id -> dept_id
        user_dept[user_id] = dept_id
        await message.answer(
            "✅ Я запомнил ваш отдел. Теперь напишите мне в личные сообщения /start, чтобы получить меню.\n"
            "Или просто перейдите по ссылке ниже:\n"
            f"https://t.me/{bot.username}?start={SECRET_GROUP_TOKEN}"
        )
        return

    # Если это личный чат с параметром (глубокая ссылка) – связываем
    if message.chat.type == "private" and deep_link_param == SECRET_GROUP_TOKEN:
        # Здесь можно было бы спросить chat_id группы, но для простоты предложим ввести вручную
        await message.answer(
            "Для привязки к отделу отправьте мне номер chat_id группы.\n"
            "Вы можете узнать его, написав в группе /chatid (если добавите такого бота).\n"
            "Пока оставим как есть – выберите отдел из меню, когда он появится."
        )
        # Временно: показываем меню без привязки (но тогда вакансии не покажутся)
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(text="📋 Активные вакансии", callback_data="menu_vacancies"))
        builder.add(InlineKeyboardButton(text="📂 Архивные вакансии", callback_data="menu_archive"))
        builder.add(InlineKeyboardButton(text="❓ Помощь", callback_data="menu_help"))
        await message.answer("Меню (пока без привязки к отделу):", reply_markup=builder.as_markup())
        return

# ---------- Главное меню (по callback'ам) ----------
@dp.callback_query(lambda c: c.data == "menu_vacancies")
async def menu_vacancies(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    dept_id = user_dept.get(user_id)
    if not dept_id:
        await callback.answer("Сначала запустите бота в группе командой /start", show_alert=True)
        return
    vacancies = get_vacancies_for_department(dept_id, only_active=True)
    if not vacancies:
        await callback.message.answer("Нет активных вакансий.")
        await callback.answer()
        return
    builder = InlineKeyboardBuilder()
    for v in vacancies:
        count = len(v.get("candidates", []))
        builder.add(InlineKeyboardButton(text=f"{v['title']} ({count})", callback_data=f"vacancy_{v['id']}"))
    await callback.message.edit_text("📋 Активные вакансии:", reply_markup=builder.as_markup())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_archive")
async def menu_archive(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    dept_id = user_dept.get(user_id)
    if not dept_id:
        await callback.answer("Сначала запустите бота в группе командой /start", show_alert=True)
        return
    vacancies = get_vacancies_for_department(dept_id, only_active=False)
    inactive = [v for v in vacancies if not v.get("active", True)]
    if not inactive:
        await callback.message.answer("Нет архивных вакансий.")
        await callback.answer()
        return
    builder = InlineKeyboardBuilder()
    for v in inactive:
        builder.add(InlineKeyboardButton(text=v["title"], callback_data=f"activate_{v['id']}"))
    await callback.message.edit_text("📂 Архивные вакансии (нажмите для активации):", reply_markup=builder.as_markup())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_help")
async def menu_help(callback: types.CallbackQuery):
    text = (
        "📖 <b>Справка</b>\n\n"
        "• /start — начать работу в группе\n"
        "• под сообщением о кандидате — кнопки статуса и комментария\n"
        "• комментарий: кнопка 💬 или ответ (reply) на карточку кандидата\n"
        "• в личном чате — просмотр вакансий и кандидатов\n"
        "• деактивация вакансий — только администратору"
    )
    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.answer()

# ---------- Показать кандидатов по вакансии ----------
@dp.callback_query(lambda c: c.data.startswith("vacancy_"))
async def show_vacancy(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    vacancy_id = int(callback.data.split("_")[1])
    vacancies = load_vacancies()
    vacancy = next((v for v in vacancies if v["id"] == vacancy_id), None)
    if not vacancy:
        await callback.message.answer("Вакансия не найдена")
        await callback.answer()
        return
    # Сохраняем состояние (пагинация, поиск)
    user_state = {"vacancy_id": vacancy_id, "page": 0, "keyword": None}
    # Временно храним в словаре (можно глобально)
    if not hasattr(show_vacancy, "state"):
        show_vacancy.state = {}
    show_vacancy.state[user_id] = user_state
    await send_candidates_page(callback.message, user_id, vacancy_id, page=0)
    await callback.answer()

async def send_candidates_page(message: types.Message, user_id: int, vacancy_id, page=0, keyword=None):
    vacancies = load_vacancies()
    vacancy = next((v for v in vacancies if v["id"] == vacancy_id), None)
    if not vacancy:
        await message.answer("Вакансия не найдена")
        return

    candidates = vacancy.get("candidates", [])
    if keyword:
        kw_low = keyword.lower()
        candidates = [c for c in candidates if
                      kw_low in c.get("name", "").lower() or
                      kw_low in c.get("hr_comment", "").lower() or
                      kw_low in c.get("resume_link", "").lower() or
                      kw_low in c.get("video_link", "").lower() or
                      kw_low in c.get("task_link", "").lower()]
    total = len(candidates)
    page_size = 5
    start = page * page_size
    end = start + page_size
    candidates_page = candidates[start:end]

    text = f"<b>{vacancy['title']}</b>\n"
    if keyword:
        text += f"🔍 Поиск: «{keyword}»\n"
    text += f"📊 Показано {start+1}-{min(end, total)} из {total}\n\n"
    if not candidates_page:
        text += "Нет кандидатов."
    else:
        for idx, cand in enumerate(candidates_page, start=1):
            text += f"{start+idx}. {cand.get('name', 'Без имени')}\n"
            if cand.get("resume_link"):
                text += f"   📄 <a href='{cand['resume_link']}'>Резюме</a>\n"
            if cand.get("video_link"):
                text += f"   🎥 <a href='{cand['video_link']}'>Видео</a>\n"
            if cand.get("task_link"):
                text += f"   ✅ <a href='{cand['task_link']}'>Задание</a>\n"
            if cand.get("hr_comment"):
                text += f"   💬 {cand['hr_comment']}\n"
            text += "\n"

    builder = InlineKeyboardBuilder()
    if page > 0:
        builder.add(InlineKeyboardButton(text="◀ Назад", callback_data=f"page_{vacancy_id}_{page-1}_{keyword or ''}"))
    if end < total:
        builder.add(InlineKeyboardButton(text="Вперед ▶", callback_data=f"page_{vacancy_id}_{page+1}_{keyword or ''}"))
    builder.row(InlineKeyboardButton(text="🔍 Поиск", callback_data=f"search_{vacancy_id}"))
    builder.add(InlineKeyboardButton(text="📊 Статистика", callback_data=f"stats_{vacancy_id}"))
    builder.add(InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu_vacancies"))

    # Если пользователь – админ, добавляем кнопки управления вакансией
    if user_id == _admin_user_id():
        if vacancy.get("active", True):
            builder.add(InlineKeyboardButton(text="❌ Сделать неактивной", callback_data=f"deactivate_{vacancy_id}"))
        else:
            builder.add(InlineKeyboardButton(text="✅ Активировать", callback_data=f"activate_{vacancy_id}"))

    await message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML", disable_web_page_preview=True)

# ---------- Пагинация ----------
@dp.callback_query(lambda c: c.data.startswith("page_"))
async def paginate(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    vacancy_id = int(parts[1])
    page = int(parts[2])
    keyword = parts[3] if parts[3] != "" else None
    # Получаем сохранённое состояние пользователя (можно из глобального словаря)
    user_state = getattr(show_vacancy, "state", {}).get(callback.from_user.id, {})
    # Обновляем
    await send_candidates_page(callback.message, callback.from_user.id, vacancy_id, page, keyword)
    await callback.answer()

# ---------- Поиск ----------
@dp.callback_query(lambda c: c.data.startswith("search_"))
async def ask_search(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    vacancy_id = int(callback.data.split("_")[1])
    # Сохраняем состояние, что ожидаем поиск
    if not hasattr(ask_search, "search_state"):
        ask_search.search_state = {}
    ask_search.search_state[user_id] = {"vacancy_id": vacancy_id, "waiting": True}
    await callback.message.answer("Введите ключевое слово для поиска:")
    await callback.answer()

@dp.message(F.text, ~F.text.startswith("/"))
async def handle_search_query(message: types.Message):
    if await try_handle_pending_comment(message):
        return
    user_id = message.from_user.id
    if hasattr(ask_search, "search_state") and user_id in ask_search.search_state:
        state = ask_search.search_state[user_id]
        if state.get("waiting"):
            keyword = message.text.strip()
            vacancy_id = state["vacancy_id"]
            del ask_search.search_state[user_id]
            await send_candidates_page(message, user_id, vacancy_id, page=0, keyword=keyword)
            try:
                await message.delete()
            except Exception:
                pass
            return

# ---------- Статистика ----------
@dp.callback_query(lambda c: c.data.startswith("stats_"))
async def show_stats(callback: types.CallbackQuery):
    vacancy_id = int(callback.data.split("_")[1])
    vacancies = load_vacancies()
    vacancy = next((v for v in vacancies if v["id"] == vacancy_id), None)
    if not vacancy:
        await callback.message.answer("Ошибка")
        await callback.answer()
        return
    candidates = vacancy.get("candidates", [])
    total = len(candidates)
    with_video = sum(1 for c in candidates if c.get("video_link"))
    with_task = sum(1 for c in candidates if c.get("task_link"))
    with_comment = sum(1 for c in candidates if c.get("hr_comment"))
    text = f"📊 <b>Статистика по вакансии «{vacancy['title']}»</b>\n\n"
    text += f"👥 Всего кандидатов: {total}\n"
    text += f"🎥 С видео: {with_video}\n"
    text += f"✅ С выполненным заданием: {with_task}\n"
    text += f"💬 С комментарием рекрутера: {with_comment}\n"
    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.answer()

# ---------- Деактивация / активация (только для админа) ----------
@dp.callback_query(lambda c: c.data.startswith("deactivate_"))
async def deactivate_vacancy(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if user_id != _admin_user_id():
        await callback.answer("У вас нет прав на это действие", show_alert=True)
        return
    vacancy_id = int(callback.data.split("_")[1])
    vacancies = load_vacancies()
    for v in vacancies:
        if v["id"] == vacancy_id:
            v["active"] = False
            save_vacancies(vacancies)
            await callback.answer("Вакансия деактивирована", show_alert=True)
            # Обновляем текущее сообщение (убираем кнопку)
            await callback.message.edit_text(callback.message.html_text, parse_mode="HTML")
            return
    await callback.answer("Ошибка")

@dp.callback_query(lambda c: c.data.startswith("activate_"))
async def activate_vacancy(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if user_id != _admin_user_id():
        await callback.answer("У вас нет прав на это действие", show_alert=True)
        return
    vacancy_id = int(callback.data.split("_")[1])
    vacancies = load_vacancies()
    for v in vacancies:
        if v["id"] == vacancy_id:
            v["active"] = True
            save_vacancies(vacancies)
            await callback.answer("Вакансия активирована", show_alert=True)
            await callback.message.edit_text(callback.message.html_text, parse_mode="HTML")
            return
    await callback.answer("Ошибка")

# ---------- Напоминания о собеседованиях ----------
async def interview_reminder_loop():
    while True:
        try:
            results = await asyncio.to_thread(process_interview_reminders)
            for line in results:
                logging.info("interview_reminder: %s", line)
        except Exception as e:
            logging.exception("interview_reminder_loop: %s", e)
        await asyncio.sleep(60)


# ---------- Запуск ----------
async def main():
    logging.basicConfig(level=logging.INFO)
    await bot.delete_webhook(drop_pending_updates=False)
    logger.info("Webhook сброшен, запуск polling для @%s", (await bot.get_me()).username)
    asyncio.create_task(interview_reminder_loop())
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

if __name__ == "__main__":
    asyncio.run(main())