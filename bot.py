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
    RECOMMENDATION,
    CLARIFICATION,
    PROGRAM,
) = range(10)


# ─── Perplexity helper ────────────────────────────────────────────────────────

async def ask_perplexity(messages: list[dict]) -> str:
    """Отправляет сообщения в Perplexity API и возвращает ответ."""
    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "sonar-pro",
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 2000,
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


# ─── /start ───────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
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
        "Например: август 2025, конец июля, 10–20 сентября"
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
        "⏳ Анализирую ваш профиль и подбираю варианты… Это займёт несколько секунд.",
        reply_markup=ReplyKeyboardRemove(),
    )

    messages = [
        {
            "role": "system",
            "content": (
                "Ты — опытный тревел-консультант. Отвечаешь строго на русском языке. "
                "Давай конкретные, актуальные рекомендации с реальными названиями мест и отелей. "
                "Структурируй ответ с emoji для удобства чтения в Telegram."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Подбери 3 варианта путешествия для следующего профиля:\n{profile}\n\n"
                "Для каждого варианта укажи:\n"
                "1. 🌍 Страна и конкретное место/курорт\n"
                "2. 🏖 Тип тура (пляжный, экскурсионный, горный и т.д.)\n"
                "3. ✅ Почему подходит этому путешественнику\n"
                "4. 💰 Примерная стоимость (в рублях)\n\n"
                "В конце спроси, какой вариант интересует больше всего, "
                "и предложи задать уточняющие вопросы по программе."
            ),
        },
    ]

    try:
        reply = await ask_perplexity(messages)
    except Exception as e:
        logger.error(f"Perplexity error: {e}")
        reply = "Извините, произошла ошибка при получении рекомендаций. Попробуйте позже."

    context.user_data["recommendation"] = reply
    context.user_data["messages_history"] = messages + [{"role": "assistant", "content": reply}]

    await update.message.reply_text(reply)
    await update.message.reply_text(
        "💬 Напишите номер понравившегося варианта (1, 2 или 3) "
        "или задайте любой уточняющий вопрос. "
        "Когда будете готовы к полной программе, напишите: *программа*",
        parse_mode="Markdown",
    )
    return CLARIFICATION


async def clarification(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_text = update.message.text.strip()

    if user_text.lower() in ("программа", "составь программу", "детальная программа", "хочу программу"):
        return await generate_program(update, context)

    history = context.user_data.get("messages_history", [])
    history.append({"role": "user", "content": user_text})

    await update.message.reply_text("⏳ Уточняю детали…")

    try:
        reply = await ask_perplexity(history)
    except Exception as e:
        logger.error(f"Perplexity error: {e}")
        reply = "Ошибка при обработке запроса. Попробуйте ещё раз."

    history.append({"role": "assistant", "content": reply})
    context.user_data["messages_history"] = history

    await update.message.reply_text(reply)
    await update.message.reply_text(
        "Можете задать ещё вопросы или напишите *программа* — и я составлю детальный план поездки.",
        parse_mode="Markdown",
    )
    return CLARIFICATION


async def generate_program(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    profile = build_profile_summary(context.user_data)
    history = context.user_data.get("messages_history", [])

    await update.message.reply_text(
        "⏳ Составляю подробную программу поездки с отелями, трансфером и авиабилетами… "
        "Это займёт около 15 секунд."
    )

    history.append(
        {
            "role": "user",
            "content": (
                f"Составь детальную программу поездки на основе нашего разговора и профиля:\n{profile}\n\n"
                "Программа должна включать:\n\n"
                "✈️ *АВИАБИЛЕТЫ*\n"
                "— Конкретные рейсы (авиакомпания, маршрут, примерная цена в рублях)\n"
                "— Лучшие сайты для покупки (Aviasales, S7, Aeroflot и т.д.)\n\n"
                "🏨 *ОТЕЛИ*\n"
                "— 3 конкретных отеля с названиями, звёздностью и примерной ценой за ночь\n"
                "— Ссылки на Booking.com или Ostrovok\n\n"
                "🚗 *ТРАНСФЕР*\n"
                "— Как добраться из аэропорта до отеля\n"
                "— Примерная стоимость такси/трансфера\n\n"
                "📅 *ПРОГРАММА ПО ДНЯМ*\n"
                "— Детальный план каждого дня с конкретными достопримечательностями, ресторанами и активностями\n\n"
                "💡 *СОВЕТЫ*\n"
                "— Что взять с собой, лучшее время для посещения мест, местные лайфхаки\n\n"
                "💰 *ИТОГОВЫЙ БЮДЖЕТ*\n"
                "— Разбивка расходов: авиа + отель + питание + экскурсии + прочее"
            ),
        }
    )

    try:
        reply = await ask_perplexity(history)
    except Exception as e:
        logger.error(f"Perplexity error: {e}")
        reply = "Ошибка при составлении программы. Пожалуйста, попробуйте снова через минуту."

    history.append({"role": "assistant", "content": reply})
    context.user_data["messages_history"] = history

    # Telegram ограничивает сообщения 4096 символами — разбиваем при необходимости
    max_len = 4000
    for i in range(0, len(reply), max_len):
        await update.message.reply_text(reply[i : i + max_len])

    await update.message.reply_text(
        "🎉 Программа готова! Если хотите что-то изменить или уточнить — просто напишите.\n"
        "Чтобы начать заново, введите /start"
    )
    return PROGRAM


async def program_followup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка вопросов после составления программы."""
    user_text = update.message.text.strip()
    if user_text.startswith("/"):
        return PROGRAM

    history = context.user_data.get("messages_history", [])
    history.append({"role": "user", "content": user_text})

    await update.message.reply_text("⏳ Обновляю программу…")

    try:
        reply = await ask_perplexity(history)
    except Exception as e:
        logger.error(f"Perplexity error: {e}")
        reply = "Ошибка. Попробуйте ещё раз."

    history.append({"role": "assistant", "content": reply})
    context.user_data["messages_history"] = history

    for i in range(0, len(reply), 4000):
        await update.message.reply_text(reply[i : i + 4000])

    return PROGRAM


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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
            RECOMMENDATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, clarification)],
            CLARIFICATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, clarification)],
            PROGRAM: [MessageHandler(filters.TEXT & ~filters.COMMAND, program_followup)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler("start", start))

    logger.info("Бот запущен...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
