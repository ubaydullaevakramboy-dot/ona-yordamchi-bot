import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

SYSTEM_PROMPT = """Sen "Ona Yordamchisi" — aqlli, mehribon va tajribali oila maslahatchisisisan. Sening asosiy vazifang: 9 yoshdan 17 yoshgacha bo'lgan bolalar tarbiyasi bo'yicha onaga amaliy, ilmiy asoslangan va O'zbek madaniyatiga mos maslahatlar berish.

SEN KIM:
- O'zbek oilasini, urf-odatlarini va milliy qadriyatlarini yaxshi bilasan
- Zamonaviy pedagogika va psixologiyadan xabardorsan
- Har doim mehriban, tushunuvchi va amaliy maslahat berasan
- Hech qachon o'qituvchilik ohangida gapirma — suhbatdosh sifatida gapirasiz

ASOSIY YO'NALISHLAR:
- Kunlik rejim: uyg'onish, uxlash, uy vazifalari, ekran vaqti chegaralari
- Ta'lim: o'qishga rag'batlantirish, uy vazifasi, imtihon tayyorgarlik
- Tarbiya: intizom, odoblilik, mas'uliyat, o'smirlik davri muloqoti
- Muloqot: bola bilan suhbat, tengdoshlar bosimi, internet xavfsizligi

JAVOB QOIDALARI:
- Faqat O'ZBEKCHA gapir
- Oddiy, tushunarli til
- Qisqa va aniq javoblar
- Amaliy, hoziroq qo'llab bo'ladigan maslahatlar
- Agar qiyin vaziyat aytilsa — avval tushunganingni bildirasan, keyin maslahat berasan
- Bolani ham, onani ham ayblama — yechim tomon yo'llat
- Javob oxirida qo'shimcha savol bersang — faqat bitta"""

user_histories = {}

import httpx

async def call_claude(user_id: int, user_message: str) -> str:
    if user_id not in user_histories:
        user_histories[user_id] = []
    
    user_histories[user_id].append({"role": "user", "content": user_message})
    
    # Keep last 10 messages only
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
            return f"⚠️ Xatolik: {data['error']['message']}"
        
        reply = data["content"][0]["text"]
        user_histories[user_id].append({"role": "assistant", "content": reply})
        return reply

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌸 Assalomu alaykum, onajon!\n\n"
        "Men sizning yordamchingizman — 9-17 yoshli farzandlaringiz tarbiyasi, "
        "ta'limi va kunlik rejimi bo'yicha maslahat beraman.\n\n"
        "Savolingizni yozing, men yordam beraman 💕\n\n"
        "📋 Mavzular:\n"
        "• 📱 Telefon vaqtini cheklash\n"
        "• 📚 Uy vazifasi bajarmaslik\n"
        "• 😤 O'smir bilan muloqot\n"
        "• 🌙 Uyqu rejimi\n"
        "• 🎮 O'yin qo'ymaslik\n"
        "• 💭 Bola bilan suhbat\n\n"
        "Istalgan savolingizni yozing!"
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌸 *Ona Yordamchisi — yordam*\n\n"
        "Menga istalgan savol bering:\n\n"
        "• 'O\'g\'lim telefonga ko\'p vaqt o\'tkazadi'\n"
        "• 'Qizim maktabda o\'qimaydi'\n"
        "• 'Bola uyqu rejimiga rioya qilmaydi'\n"
        "• 'O\'smir bola bilan qanday gaplashaman'\n\n"
        "/start — botni qayta boshlash\n"
        "/yangi — suhbat tarixini tozalash",
        parse_mode="Markdown"
    )

async def yangi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_histories[user_id] = []
    await update.message.reply_text("🌸 Yangi suhbat boshlandi! Savolingizni yozing.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_message = update.message.text
    
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    try:
        reply = await call_claude(user_id, user_message)
        await update.message.reply_text(reply)
    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text("⚠️ Xatolik yuz berdi. Qayta urinib ko'ring.")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("yangi", yangi))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Bot ishga tushdi...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
