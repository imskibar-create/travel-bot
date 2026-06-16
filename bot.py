import os
import logging
import httpx
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    filters,
    ContextTypes,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
PERPLEXITY_API_KEY = os.environ["PERPLEXITY_API_KEY"]
PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"

# Состояния диалога
(
    AGE,
    GENDER,
    INTERESTS,
    GROUP_TYPE,
    BUDGET,
    DATES,
    DURATION,
    CLARIFICATION,
    PROGRAM,
) = range(9)


# ─── Perplexity helper ────────────────────────────────────────────────────────

async def ask_perplexity(messages: list[dict], max_tokens: int = 1200) -> str:
    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "sonar",
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": max_tokens,
    }
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(PERPLEXITY_API_URL, json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


def build_profile_summary(data: dict) -> str:
    group_map = {
        "один": "путешествую один",
        "компания": "с компанией друзей",
        "пара": "путешествую парой",
        "семья": "с семьёй (есть дети)",
    }
    group_str = group_map.get(data.get("group_type", ""), data.get("group_type", ""))
    return (
        f"Возраст: {data.get('age')}, пол: {data.get('gender')}, "
        f"увлечения: {data.get('interests')}, "
        f"состав группы: {group_str}, "
        f"бюджет: {data.get('budget')} руб., "
        f"даты: {data.get('dates')}, "
        f"длительность: {data.get('duration')} дней."
    )


def reset_user_data(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Полный сброс данных пользователя."""
    context.user_data.clear()
    context.user_data["messages_history"] = []


# ─── /start ───────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    reset_user_data(context)
    await update.message.reply_text(
        "👋 Привет! Я помогу подобрать идеальное путешествие.\n\n"
        "Отвечу на несколько вопросов — и предложу страну, место и тип тура, "
        "а потом составлю подробную программу с отелями, трансфером и авиабилетами.\n\n"
        "Сколько вам лет?",
        reply_markup=ReplyKeyboardRemove(),
    )
    return AGE


# ─── Шаги опросника ──────────────────────────────────────────────────────────

async def age(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if not text.isdigit() or not (5 <= int(text) <= 120):
        await update.message.reply_text("Пожалуйста, введите возраст цифрой (например: 28).")
        return AGE
    context.user_data["age"] = text
    keyboard = [["Мужчина", "Женщина"]]
    await update.message.reply_text(
        "Ваш пол?",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True),
    )
    return GENDER


async def gender(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["gender"] = update.message.text.strip().lower()
    await update.message.reply_text(
        "Расскажите о своих увлечениях и интересах.\n"
        "Например: пляжный отдых, горы, история, гастрономия, активный спорт, шопинг, природа…",
        reply_markup=ReplyKeyboardRemove(),
    )
    return INTERESTS


async def interests(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["interests"] = update.message.text.strip()
    keyboard = [["Один", "Компания"], ["Пара", "Семья"]]
    await update.message.reply_text(
        "С кем планируете поехать?",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True),
    )
    return GROUP_TYPE


async def group_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["group_type"] = update.message.text.strip().lower()
    await update.message.reply_text(
        "Какой у вас бюджет на поездку? Укажите сумму в рублях на человека.\n"
        "Например: 80000",
        reply_markup=ReplyKeyboardRemove(),
    )
    return BUDGET


async def budget(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip().replace(" ", "").replace(",", "")
    if not text.isdigit():
        await update.message.reply_text("Введите сумму цифрами, например: 150000")
        return BUDGET
    context.user_data["budget"] = text
    await update.message.reply_text(
        "Когда планируете поехать? Укажите примерные даты или месяц.\n"
        "Например: август 2026, конец июля, 10–20 сентября"
    )
    return DATES


async def dates(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["dates"] = update.message.text.strip()
    await update.message.reply_text(
        "На сколько дней планируете поездку?\n"
        "Например: 7, 10, 14"
    )
    return DURATION


async def duration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if not text.isdigit() or int(text) <= 0:
        await update.message.reply_text("Укажите количество дней цифрой, например: 10")
        return DURATION
    context.user_data["duration"] = text

    profile = build_profile_summary(context.user_data)
    await update.message.reply_text(
        "⏳ Подбираю варианты… Это займёт несколько секунд.",
        reply_markup=ReplyKeyboardRemove(),
    )

    messages = [
        {
            "role": "system",
            "content": (
                "Ты — опытный тревел-консультант. Отвечаешь строго на русском языке. "
                "Давай конкретные рекомендации с реальными названиями мест. "
                "Используй emoji для удобства чтения в Telegram. "
                "Отвечай лаконично — не более 600 слов."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Подбери 3 варианта путешествия для профиля:\n{profile}\n\n"
                "Для каждого варианта:\n"
                "1. 🌍 Страна и конкретное место\n"
                "2. 🏖 Тип тура\n"
                "3. ✅ Почему подходит\n"
                "4. 💰 Примерная стоимость в рублях\n\n"
                "В конце спроси, какой вариант интереснее, и предложи написать «программа» для детального плана."
            ),
        },
    ]

    try:
        reply = await ask_perplexity(messages, max_tokens=900)
    except Exception as e:
        logger.error(f"Perplexity error: {e}")
        reply = "Извините, произошла ошибка. Попробуйте ещё раз — введите /start."

    context.user_data["messages_history"] = messages + [{"role": "assistant", "content": reply}]

    await update.message.reply_text(reply)
    await update.message.reply_text(
        "💬 Выберите вариант (1, 2 или 3), задайте уточняющий вопрос "
        "или напишите *программа* для детального плана поездки.",
        parse_mode="Markdown",
    )
    return CLARIFICATION


# ─── Уточняющие вопросы ───────────────────────────────────────────────────────

async def clarification(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_text = update.message.text.strip()

    if user_text.lower() in ("программа", "составь программу", "детальная программа", "хочу программу"):
        return await generate_program(update, context)

    history = context.user_data.get("messages_history", [])
    if not history:
        await update.message.reply_text("Диалог сброшен. Введите /start чтобы начать заново.")
        return ConversationHandler.END

    history.append({"role": "user", "content": user_text})
    await update.message.reply_text("⏳ Уточняю…")

    try:
        reply = await ask_perplexity(history, max_tokens=700)
    except Exception as e:
        logger.error(f"Perplexity error: {e}")
        reply = "Ошибка. Попробуйте ещё раз."

    history.append({"role": "assistant", "content": reply})
    context.user_data["messages_history"] = history

    await update.message.reply_text(reply)
    await update.message.reply_text(
        "Задайте ещё вопрос или напишите *программа* для детального плана.",
        parse_mode="Markdown",
    )
    return CLARIFICATION


# ─── Генерация программы ─────────────────────────────────────────────────────

async def generate_program(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    profile = build_profile_summary(context.user_data)
    history = context.user_data.get("messages_history", [])

    await update.message.reply_text(
        "⏳ Составляю программу поездки… Это займёт около 20 секунд."
    )

    history.append(
        {
            "role": "user",
            "content": (
                f"Составь детальную программу поездки. Профиль:\n{profile}\n\n"
                "Включи:\n"
                "✈️ АВИАБИЛЕТЫ — рейсы, авиакомпании, примерные цены в рублях, сайты покупки\n"
                "🏨 ОТЕЛИ — 3 конкретных отеля с названием, звёздностью, ценой за ночь\n"
                "🚗 ТРАНСФЕР — как добраться из аэропорта, стоимость\n"
                "📅 ПРОГРАММА ПО ДНЯМ — конкретные места, рестораны, активности\n"
                "💰 ИТОГОВЫЙ БЮДЖЕТ — разбивка: авиа, отель, питание, экскурсии\n"
                "💡 3–5 практических советов\n\n"
                "Отвечай на русском языке, лаконично и структурированно."
            ),
        }
    )

    try:
        reply = await ask_perplexity(history, max_tokens=1800)
    except Exception as e:
        logger.error(f"Perplexity error: {e}")
        reply = "Ошибка при составлении программы. Попробуйте ещё раз."

    history.append({"role": "assistant", "content": reply})
    context.user_data["messages_history"] = history

    # Разбиваем длинный ответ на части (лимит Telegram — 4096 символов)
    for i in range(0, len(reply), 4000):
        await update.message.reply_text(reply[i: i + 4000])

    await update.message.reply_text(
        "🎉 Программа готова! Можете уточнить любые детали.\n"
        "Чтобы начать заново — введите /start"
    )
    return PROGRAM


async def program_followup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_text = update.message.text.strip()

    history = context.user_data.get("messages_history", [])
    if not history:
        await update.message.reply_text("Введите /start чтобы начать заново.")
        return ConversationHandler.END

    history.append({"role": "user", "content": user_text})
    await update.message.reply_text("⏳ Обновляю…")

    try:
        reply = await ask_perplexity(history, max_tokens=900)
    except Exception as e:
        logger.error(f"Perplexity error: {e}")
        reply = "Ошибка. Попробуйте ещё раз."

    history.append({"role": "assistant", "content": reply})
    context.user_data["messages_history"] = history

    for i in range(0, len(reply), 4000):
        await update.message.reply_text(reply[i: i + 4000])

    return PROGRAM


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    reset_user_data(context)
    await update.message.reply_text(
        "Отменено. Введите /start чтобы начать заново.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


# ─── main ─────────────────────────────────────────────────────────────────────

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, age)],
            GENDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, gender)],
            INTERESTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, interests)],
            GROUP_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, group_type)],
            BUDGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, budget)],
            DATES: [MessageHandler(filters.TEXT & ~filters.COMMAND, dates)],
            DURATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, duration)],
            CLARIFICATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, clarification)],
            PROGRAM: [MessageHandler(filters.TEXT & ~filters.COMMAND, program_followup)],
        },
        # /start и /cancel работают из любого состояния
        fallbacks=[
            CommandHandler("start", start),
            CommandHandler("cancel", cancel),
        ],
        allow_reentry=True,
        per_message=False,
        per_chat=True,
    )

    app.add_handler(conv)

    logger.info("Бот запущен...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
