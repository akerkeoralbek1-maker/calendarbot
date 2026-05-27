import os
from datetime import datetime, timedelta

from dotenv import load_dotenv

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from agent import CalendarAgent


load_dotenv()



async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["📅 Сегодня", "📆 Завтра"],
        ["🗓 Неделя", "➕ Создать событие"],
        ["🔗 Привязать Google Calendar"]
    ]

    reply_markup = ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True
    )

    await update.message.reply_text(
        "👋 Привет! Я твой календарь-ассистент.\n\n"
        "Выбери кнопку или напиши текстом:",
        reply_markup=reply_markup
    )

async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    job = context.job

    await context.bot.send_message(
        chat_id=job.chat_id,
        text=job.data
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text

    if user_message == "📅 Сегодня":
        user_message = "Что у меня сегодня?"

    elif user_message == "📆 Завтра":
        user_message = "Что у меня завтра?"

    elif user_message == "🗓 Неделя":
        user_message = "Что у меня на этой неделе?"

    elif user_message == "➕ Создать событие":
        await update.message.reply_text(
            "Напиши так:\n\n"
            "Создай встречу завтра в 15:00 — Созвон"
        )
        return

    elif user_message == "🔗 Привязать Google Calendar":
        user_id = update.effective_user.id

        auth_url = f"https://calendarbot-nibs.onrender.com/auth?user_id={user_id}"

        await update.message.reply_text(
            "Чтобы привязать Google Calendar, открой ссылку:\n\n"
            f"{auth_url}"
        )

        return

    user_id = update.effective_user.id

    user_agent = CalendarAgent(user_id=user_id)

    response = await user_agent.handle_message(user_message)

    if "✅ Событие создано" in response:
        lines = response.split("\n")

        event_title = "событие"
        event_date = None
        event_time = None

        for line in lines:
            if line.startswith("📌"):
                event_title = line.replace("📌", "").strip()

            if line.startswith("📅"):
                event_date = line.replace("📅", "").strip()

            if line.startswith("🕒"):
                event_time = line.replace("🕒", "").strip()

        if event_date and event_time:
            event_datetime = datetime.strptime(
                f"{event_date} {event_time}",
                "%d.%m.%Y %H:%M"
            )

            now = datetime.now()

            reminder_1_hour = event_datetime - timedelta(hours=1)
            reminder_5_min = event_datetime - timedelta(minutes=5)

            if reminder_1_hour > now:
                context.job_queue.run_once(
                    send_reminder,
                    when=(reminder_1_hour - now).total_seconds(),
                    chat_id=update.effective_chat.id,
                    data=f"⏰ Через 1 час событие:\n{event_title}"
                )

            if reminder_5_min > now:
                context.job_queue.run_once(
                    send_reminder,
                    when=(reminder_5_min - now).total_seconds(),
                    chat_id=update.effective_chat.id,
                    data=f"⏰ Через 5 минут событие:\n{event_title}"
                )

    await update.message.reply_text(response)


def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")

    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start))

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message
        )
    )

    print("✅ Бот запущен")

    app.run_polling()


if __name__ == "__main__":
    main()
