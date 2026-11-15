"""
Ona Yordamchisi — Telegram bot.
Onalarga 9–17 yoshli farzandlar tarbiyasi bo'yicha maslahat beradi.
Javoblarni Claude (Anthropic API) tayyorlaydi.

Kerakli o'zgaruvchilar (Railway → Variables):
  TELEGRAM_TOKEN     — BotFather bergan token
  ANTHROPIC_API_KEY  — console.anthropic.com dan olingan kalit
Ixtiyoriy:
  CLAUDE_MODEL       — standart: claude-sonnet-5-5
  ALLOWED_USERS      — faqat shu Telegram ID'lar foydalansin (vergul bilan), bo'sh bo'lsa hamma uchun ochiq
"""

import os
import logging
import asyncio
from collections import defaultdict

from anthropic import AsyncAnthropic, APIStatusError, APIConnectionError
from telegram import Update, ReplyKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("ona-bot")

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5").strip()
ALLOWED_USERS = {
    int(x) for x in os.environ.get("ALLOWED_USERS", "").replace(" ", "").split(",") if x.isdigit()
}

MAX_HISTORY = 20          # oxirgi 20 ta xabar (10 savol + 10 javob) eslab qolinadi
MAX_TOKENS = 1200
TG_LIMIT = 4000           # Telegram bitta xabar chegarasi 4096

SYSTEM_PROMPT = """Sen "Ona Yordamchisi"san — mehribon, tajribali oila maslahatchisi va bolalar psixologiyasini yaxshi biladigan suhbatdosh. Onalarga 9–17 yoshli farzandlari tarbiyasi bo'yicha amaliy maslahat berasan.

TIL VA USLUB
- Faqat o'zbek tilida (lotin yozuvida) javob ber. Ona rus tilida yozsa ham, o'zbekcha javob ber, faqat u aniq so'rasa ruschaga o't.
- Oddiy, iliq, hurmatli til ishlat. Onani "siz" deb murojaat qil.
- Avval onaning tashvishini tushunganingni bir-ikki gap bilan bildir, keyin maslahat ber.
- Javob qisqa va amaliy bo'lsin: 3–6 ta aniq qadam yoki tavsiya, har biri 1–2 gap. Uzun nazariya yozma.
- Bolaga aytish mumkin bo'lgan tayyor gaplarni misol qilib ber (masalan: "Farzandingizga shunday deyishingiz mumkin: ...").
- Kerak bo'lsa, bitta aniqlashtiruvchi savol ber: bolaning yoshi, o'g'il yoki qizligi, muammo qachondan beri borligi.
- Telegram uchun yoz: markdown jadval, # sarlavha ishlatma. Ro'yxat uchun "•" yoki raqam ishlat.

MAVZULAR
- Kunlik rejim, uyqu, ovqatlanish odatlari
- O'qish, uy vazifasi, maktab, repetitorlar, imtihonlar
- Tarbiya, intizom, jazo va rag'bat, uy yumushlari
- O'smir bilan muloqot, ishonch, o'tish yoshi o'zgarishlari
- Telefon, internet, o'yinlar, ijtimoiy tarmoqlar
- Aka-uka, opa-singillar o'rtasidagi janjallar
- Do'stlar, tengdoshlar bosimi, maktabda bezorilik
- Kasb tanlash, qiziqishlarni rivojlantirish
- Onaning o'z charchog'i va asabini boshqarish
Mavzudan tashqari savollarga muloyimlik bilan qisqa javob ber va tarbiya mavzusiga qaytar.

O'ZBEK OILASI KONTEKSTI
- O'zbek oilasi qadriyatlarini hurmat qil: kattalarga hurmat, oila birligi, buvi-buvalarning o'rni, mahalla.
- Maslahatlaring o'zbek oilasi hayotiga mos va amalda bajariladigan bo'lsin.

XAVFSIZLIK QOIDALARI (juda muhim)
- Bolani urish, qo'rqitish, kamsitishni hech qachon maslahat berma. Jismoniy jazo haqida so'rashsa, muloyimlik bilan zararini tushuntir va o'rniga boshqa yo'l ko'rsat.
- Tibbiy tashxis qo'yma va dori tavsiya qilma. Sog'liq belgilari bo'lsa, shifokorga (pediatr, nevrolog) borishni maslahat ber.
- Agar bola o'zini o'ldirish yoki o'ziga zarar yetkazish haqida gapirgan, o'zini kesgan, ovqatdan butunlay voz kechgan, giyohvand modda yoki spirtli ichimlik ishlatayotgan, zo'ravonlik yoki shilqimlikka uchragan bo'lishi mumkin bo'lsa:
  1) onani xotirjam bo'lishga va bolani yolg'iz qoldirmaslikka chaqir;
  2) bolani ayblamasdan, tinglash kerakligini ayt;
  3) albatta mutaxassisga — bolalar psixologi yoki psixiatriga murojaat qilishni ayt;
  4) hayot xavf ostida bo'lsa, darhol 103 (tez yordam) yoki 112 ga qo'ng'iroq qilishni ayt.
  Bunday holatda o'zing davolashga urinma, sen faqat birinchi yo'l-yo'riq berasan.
- O'zing aniq bilmagan raqam, qonun yoki tashkilot nomini o'ylab topma."""

WELCOME = (
    "Assalomu alaykum, onajon! 🌸\n\n"
    "Men Ona Yordamchisiman. 9–17 yoshli farzandlaringiz tarbiyasi bo'yicha "
    "maslahat beraman: o'qish, telefon, o'smirlik, intizom, muloqot va boshqalar.\n\n"
    "Savolingizni o'z so'zlaringiz bilan yozing yoki pastdagi mavzulardan birini tanlang.\n"
    "Bolaning yoshi va o'g'il yoki qizligini yozsangiz, maslahat aniqroq bo'ladi.\n\n"
    "/yangi — yangi suhbat boshlash\n"
    "/yordam — bot haqida"
)

HELP = (
    "ℹ️ Bot qanday ishlaydi\n\n"
    "• Savolingizni oddiy yozing, men javob beraman.\n"
    "• Oxirgi suhbatimizni eslab qolaman, shuning uchun qo'shimcha savol bera olasiz.\n"
    "• Boshqa farzand yoki boshqa mavzu haqida gaplashmoqchi bo'lsangiz, /yangi bosing.\n\n"
    "⚠️ Men shifokor yoki psixolog o'rnini bosa olmayman. "
    "Jiddiy holatlarda mutaxassisga murojaat qiling. Shoshilinch holatda: 103 yoki 112."
)

TOPIC_BUTTONS = [
    ["📱 Telefonga bog'lanib qolgan", "📚 Dars qilmayapti"],
    ["😤 Gap qaytaradi, qaysar", "😴 Kech yotadi, rejim yo'q"],
    ["🤐 Men bilan gaplashmaydi", "👫 Aka-uka janjallashadi"],
]
TOPIC_PROMPTS = {
    "📱 Telefonga bog'lanib qolgan": "Farzandim telefondan uzoqlasha olmayapti, kun bo'yi telefonda. Nima qilsam bo'ladi?",
    "📚 Dars qilmayapti": "Farzandim dars qilishni xohlamayapti, uy vazifasini qilmaydi. Qanday yondashay?",
    "😤 Gap qaytaradi, qaysar": "Farzandim gap qaytaradi, aytganimni qilmaydi, qaysar bo'lib qolgan. Nima qilay?",
    "😴 Kech yotadi, rejim yo'q": "Farzandim kechasi kech yotadi, ertalab turolmaydi, kun tartibi yo'q. Qanday tartibga solsam bo'ladi?",
    "🤐 Men bilan gaplashmaydi": "Farzandim men bilan gaplashmay qo'ydi, xonasiga kirib olib, hech narsa aytmaydi. Qanday yaqinlashsam bo'ladi?",
    "👫 Aka-uka janjallashadi": "Farzandlarim bir-biri bilan doim janjallashadi. Ularni qanday yarashtirsam bo'ladi?",
}
KEYBOARD = ReplyKeyboardMarkup(TOPIC_BUTTONS, resize_keyboard=True, input_field_placeholder="Savolingizni yozing...")

client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY, max_retries=3, timeout=60)
histories: dict[int, list[dict]] = defaultdict(list)
locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)


def trim_history(h: list[dict]) -> list[dict]:
    """Tarixni qisqartiradi va har doim 'user' xabari bilan boshlanishini ta'minlaydi."""
    h = h[-MAX_HISTORY:]
    while h and h[0]["role"] != "user":
        h = h[1:]
    return h


def split_text(text: str, limit: int = TG_LIMIT) -> list[str]:
    parts = []
    while len(text) > limit:
        cut = text.rfind("\n", 0, limit)
        if cut < limit // 2:
            cut = text.rfind(" ", 0, limit)
        if cut <= 0:
            cut = limit
        parts.append(text[:cut].strip())
        text = text[cut:].strip()
    if text:
        parts.append(text)
    return parts


async def ask_claude(user_id: int, user_message: str) -> str:
    history = histories[user_id]
    messages = trim_history(history + [{"role": "user", "content": user_message}])
    resp = await client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=messages,
    )
    reply = "".join(b.text for b in resp.content if b.type == "text").strip()
    if not reply:
        reply = "Kechirasiz, javob tayyorlay olmadim. Savolni boshqacharoq yozib ko'ring."
    # Faqat muvaffaqiyatli javobdan keyin tarixga yoziladi
    histories[user_id] = trim_history(messages + [{"role": "assistant", "content": reply}])
    return reply


def allowed(update: Update) -> bool:
    return not ALLOWED_USERS or (update.effective_user and update.effective_user.id in ALLOWED_USERS)


async def keep_typing(bot, chat_id: int, stop: asyncio.Event):
    while not stop.is_set():
        try:
            await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        except Exception:
            pass
        try:
            await asyncio.wait_for(stop.wait(), timeout=4)
        except asyncio.TimeoutError:
            pass


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update):
        await update.message.reply_text("Kechirasiz, bu bot shaxsiy foydalanish uchun.")
        return
    histories[update.effective_user.id] = []
    await update.message.reply_text(WELCOME, reply_markup=KEYBOARD)


async def yangi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update):
        return
    histories[update.effective_user.id] = []
    await update.message.reply_text(
        "🆕 Yangi suhbat boshlandi. Qaysi farzandingiz haqida gaplashamiz?", reply_markup=KEYBOARD
    )


async def yordam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP, reply_markup=KEYBOARD)


async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Sizning Telegram ID: {update.effective_user.id}")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update):
        await update.message.reply_text("Kechirasiz, bu bot shaxsiy foydalanish uchun.")
        return
    user_id = update.effective_user.id
    text = update.message.text.strip()
    text = TOPIC_PROMPTS.get(text, text)

    stop = asyncio.Event()
    typing_task = asyncio.create_task(keep_typing(context.bot, update.effective_chat.id, stop))
    try:
        async with locks[user_id]:
            reply = await ask_claude(user_id, text)
    except APIStatusError as e:
        logger.error("Anthropic API xatosi %s: %s", e.status_code, e.message)
        if e.status_code in (401, 403):
            reply = "⚙️ Botda sozlash xatosi bor (API kalit). Admin bilan bog'laning."
        elif e.status_code == 400 and "credit" in str(e.message).lower():
            reply = "⚙️ Bot hisobida mablag' tugagan. Admin bilan bog'laning."
        else:
            reply = "Hozir server band. Bir daqiqadan keyin qayta yozib ko'ring 🙏"
    except APIConnectionError as e:
        logger.error("Ulanish xatosi: %s", e)
        reply = "Internet bilan bog'lanishda muammo bo'ldi. Qayta urinib ko'ring 🙏"
    except Exception:
        logger.exception("Kutilmagan xato")
        reply = "Xatolik yuz berdi. Qayta urinib ko'ring 🙏"
    finally:
        stop.set()
        await typing_task

    for part in split_text(reply):
        await update.message.reply_text(part, reply_markup=KEYBOARD)


async def other_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hozircha faqat yozma xabarlarni tushunaman. Savolingizni matn bilan yozing, iltimos ✍️"
    )


def main():
    if not TELEGRAM_TOKEN or not ANTHROPIC_API_KEY:
        raise SystemExit("TELEGRAM_TOKEN va ANTHROPIC_API_KEY o'zgaruvchilarini kiriting.")
    app = Application.builder().token(TELEGRAM_TOKEN).concurrent_updates(True).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("yangi", yangi))
    app.add_handler(CommandHandler("yordam", yordam))
    app.add_handler(CommandHandler("myid", myid))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(~filters.TEXT & ~filters.COMMAND, other_content))
    logger.info("Ona Yordamchisi ishga tushdi. Model: %s", CLAUDE_MODEL)
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
