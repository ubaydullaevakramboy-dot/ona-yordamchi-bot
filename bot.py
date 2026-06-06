import os
import logging
import httpx
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

SYSTEM_PROMPT = """Sen "Ona Yordamchisi" - aqlli, mehribon va tajribali oila maslahatchisisisan. Sening asosiy vazifang: 9 yoshdan 17 yoshgacha bolgan bolalar tarbiyasi boyicha onaga amaliy, ilmiy asoslangan va Ozbekiston madaniyatiga mos maslahatlar berish.

SEN KIM:
- Ozbekiston oilasini, urf-odatlarini va milliy qadriyatlarini yaxshi bilasan
- Zamonaviy pedagogika va psixologiyadan xabardorsan
- Har doim mehriban, tushunuvchi va amaliy maslahat berasan
- Hech qachon oquvchilik ohangida gapirma

ASOSIY YONALISHLAR:
- Kunlik rejim: uyqonish, uxlash, uy vazifalari, ekran vaqti
- Talim: oqushga ragbatlantirish, uy vazifasi, imtihon tayyorgarlik
- Tarbiya: intizom, odoblilik, masuliyat, osmirlk davri muloqoti
- Muloqot: bola bilan suhbat, tengdoshlar bosimi, internet xavfsizligi

JAVOB QOIDALARI:
- Faqat OZBEKCHA gapirsiz
- Oddiy, tushunarli til
- Qisqa va aniq javoblar
- Amaliy maslahatlar
- Avval tushunganingni bildirasan, keyin maslahat berasan"""

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
        "Men sizning yordamchingizman - 9-17 yoshli farzandlaringiz tarbiyasi, "
        "talimi va kunlik rejimi boyicha maslahat beraman.\n\n"
        "Savolingizni yozing!\n\n"
        "Mavzular:\n"
        "Telefon vaqtini cheklash\n"
        "Uy vazifasi bajarmaslik\n"
        "Osmir bilan muloqot\n"
        "Uyqu rejimi\n"
        "Oyin qoymaslik\n"
        "Bola bilan suhbat"
    )

async def yangi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_histories[user_id] = []
    await update.message.reply_text("Yangi suhbat boshlandi! Savolingizni yozing.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_message = update.message.text
    
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    try:
        reply = await call_claude(user_id, user_message)
        await update.message.reply_text(reply)
    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text("Xatolik yuz berdi. Qayta urinib koring.")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("yangi", yangi))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Bot ishga tushdi...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
