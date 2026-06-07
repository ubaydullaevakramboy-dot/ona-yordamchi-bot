import os
import logging
import asyncio
import httpx
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

SYSTEM_PROMPT = """Sen Ona Yordamchisi - mehribon oila maslahatchisisisan. 9-17 yoshli bolalar tarbiyasi boyicha onaga amaliy maslahatlar ber.

QOIDALAR:
- Faqat OZBEKCHA gapirsiz
- Oddiy, tushunarli til
- Qisqa va aniq javoblar
- Avval tushunganingni bildirasan, keyin maslahat berasan

MAVZULAR:
- Kunlik rejim, uyqu
- Talim, uy vazifasi
- Tarbiya, intizom
- Osmir bilan muloqot
- Telefon va internet"""

user_histories = {}

async def call_claude(user_id: int, user_message: str) -> str:
    if user_id not in user_histories:
        user_histories[user_id] = []
    user_histories[user_id].append({"role": "user", "content": user_message})
    if len(user_histories[user_id]) > 10:
        user_histories[user_id] = user_histories[user_id][-10:]
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 800,
                "system": SYSTEM_PROMPT,
                "messages": user_histories[user_id]
            }
        )
        data = response.json()
        if "error" in data:
            return f"Xatolik: {data['error']['message']}"
        reply = data["content"][0]["text"]
        user_histories[user_id].append({"role": "assistant", "content": reply})
        return reply

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Assalomu alaykum, onajon!\n\n"
        "9-17 yoshli farzandlaringiz tarbiyasi boyicha maslahat beraman.\n\n"
        "Savolingizni yozing!\n\n"
        "/yangi - yangi suhbat boshlash"
    )

async def yangi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_histories[update.effective_user.id] = []
    await update.message.reply_text("Yangi suhbat boshlandi!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    try:
        reply = await call_claude(update.effective_user.id, update.message.text)
        await update.message.reply_text(reply)
    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text("Xatolik yuz berdi. Qayta urinib koring.")

async def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("yangi", yangi))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Bot ishga tushdi...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
