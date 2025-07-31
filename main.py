import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes,
    filters, CallbackContext
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime
from pytz import timezone

TOKEN = "ВАШ_ТОКЕН_ЗДЕСЬ"
CHAT_ID = -1002609682971  # Замените на нужный ID

MOSCOW_TZ = timezone("Europe/Moscow")

CHECKLISTS = {
    "morning": [
        "Пришли с хорошим настроением, переоделись и открыли смену в iiko",
        "Проверили внесение наличных в кассу",
        "Проверка открытия сервиса по чек-листу официанта, отправка его в общий чат",
        "Столы и подножия столов чистые",
        "Металлические поверхности натерты",
        "Стулья и диваны чистые, без крошек",
        "Все столы и стулья выставлены ровно, соблюдается симметрия",
        "Расходные материалы заполнены официантами",
        "Официанты одеты по стандарту",
        "Музыка настроена на дневной репертуар",
        "Освещение настроено на дневной сценарий",
        "Комфортная температура в зале, всё работает исправно",
        "Цветочные композиции в зале выглядят свежо",
        "Окна чистые и периметр вокруг них чистый",
        "Перед фасадом ресторана чисто, гостевая пепельница очищена",
        "Гостевые уборные чистые, все расходные материалы пополнены",
        "Отправлен план на день",
        "Отправлен утренний гоу-стоп лист по кухне",
    ],
    "day": ["Дневной чек-лист – тестовая версия. Вопрос 1", "Вопрос 2", "Вопрос 3"],
    "evening": ["Вечерний чек-лист – тестовая версия. Вопрос 1", "Вопрос 2", "Вопрос 3"],
}

user_sessions = {}

logging.basicConfig(level=logging.INFO)

async def start_checklist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    checklist_type = update.message.text.replace("/", "")
    user_id = update.effective_user.id

    user_sessions[user_id] = {
        "type": checklist_type,
        "questions": CHECKLISTS[checklist_type],
        "answers": {},
        "skipped": [],
        "current": 0,
    }

    await send_question(update, context)

async def send_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    session = user_sessions[user_id]

    questions = session["questions"]
    answers = session["answers"]
    skipped = session["skipped"]
    index = session["current"]

    while index < len(questions) and index in answers:
        index += 1

    if index < len(questions):
        session["current"] = index
        keyboard = [[KeyboardButton("Пропустить")]]
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"❓ {questions[index]}",
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        )
    elif skipped:
        session["current"] = skipped.pop(0)
        await send_question(update, context)
    else:
        await send_report(update, context)

async def handle_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_sessions:
        return

    text = update.message.text
    session = user_sessions[user_id]
    index = session["current"]

    if text.lower() == "пропустить":
        if index not in session["skipped"]:
            session["skipped"].append(index)
    else:
        session["answers"][index] = text

    session["current"] += 1
    await send_question(update, context)

async def send_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    session = user_sessions[user_id]
    checklist_name = session["type"]
    questions = session["questions"]
    answers = session["answers"]

    now = datetime.now(MOSCOW_TZ).strftime("%Y-%m-%d %H:%M")

    report = f"📋 *{checklist_name.upper()} Чек-лист* ({now})\n\n"
    for i, q in enumerate(questions):
        answer = answers.get(i, "⛔️ Без ответа")
        report += f"*{q}*\n{answer}\n\n"

    await context.bot.send_message(
        chat_id=CHAT_ID,
        text=report,
        parse_mode="Markdown"
    )
    del user_sessions[user_id]
    await update.message.reply_text("✅ Чек-лист завершён. Спасибо!")

def reminder_job_factory(checklist_type):
    async def job():
        text = {
            "morning": "☀️ Утро! Не забудьте пройти чек-лист: /morning",
            "day": "🌤 Дневной чек-лист ждет вас: /day",
            "evening": "🌙 Вечерний чек-лист доступен: /evening",
        }[checklist_type]
        app = ApplicationBuilder().token(TOKEN).build()
        await app.bot.send_message(chat_id=CHAT_ID, text=text)
    return job

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("morning", start_checklist))
    app.add_handler(CommandHandler("day", start_checklist))
    app.add_handler(CommandHandler("evening", start_checklist))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_response))

    scheduler = AsyncIOScheduler(timezone=MOSCOW_TZ)
    scheduler.add_job(reminder_job_factory("morning"), trigger='cron', hour=15, minute=31)
    scheduler.add_job(reminder_job_factory("day"), trigger='cron', hour=14, minute=0)
    scheduler.add_job(reminder_job_factory("evening"), trigger='cron', hour=20, minute=0)
    scheduler.start()

    print("✅ Бот запущен.")
    app.run_polling()

if __name__ == "__main__":
    main()
