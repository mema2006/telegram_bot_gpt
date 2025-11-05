import os
import asyncio
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, ContextTypes, filters
)
from credentials import BOT_TOKEN
from gpt import ask_gpt

# ЛОГУВАННЯ
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# СТАНИ РОЗМОВИ
MENU, GPT_MODE, TALK_MODE, QUIZ_MODE = range(4)


def load_message(name: str) -> str:
    """Завантажує текст повідомлення з файлу"""
    try:
        path = f"resources/messages/{name}.txt"
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        logger.warning(f"Файл {path} не знайдено, використовую стандартне повідомлення")
        messages = {
            "main": "👋 *Привіт!* Я твій AI-асистент.\n\nОбери дію нижче:",
            "random": "🎲 *Випадковий факт*\n\nЗараз згенерую цікавий факт!",
            "gpt": "🤖 *ChatGPT режим*\n\nНапиши своє запитання!",
            "talk": "👤 *Діалог з особистістю*\n\nОбери з ким хочеш поговорити:",
            "quiz": "❓ *Квіз*\n\nОбери тему для питань:",
        }
        return messages.get(name, f"Повідомлення для {name}")


def load_prompt(name: str) -> str:
    """Завантажує промпт з файлу"""
    try:
        path = f"resources/prompts/{name}.txt"
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        logger.warning(f"Файл {path} не знайдено, використовую стандартний промпт")
        prompts = {
            "random": "Ти експерт з цікавих фактів. Розкажи один короткий цікавий факт у 2-3 реченнях українською мовою.",
            "cobain": "Ти Курт Кобейн, музикант. Відповідай у його стилі. Говори українською.",
            "musk": "Ти Ілон Маск, підприємець та винахідник. Відповідай у його стилі. Говори українською.",
            "davinci": "Ти Леонардо да Вінчі, геній Відродження. Відповідай мудро та філософськи. Говори українською.",
            "einstein": "Ти Альберт Ейнштейн, фізик-теоретик. Пояснюй складні речі просто. Говори українською.",
        }
        return prompts.get(name, "Ти дружній асистент. Відповідай українською мовою.")


async def send_image(update: Update, context: ContextTypes.DEFAULT_TYPE, name: str):
    """Надсилає зображення"""
    try:
        path = f"resources/images/{name}.jpg"
        if os.path.exists(path):
            target = update.callback_query.message if update.callback_query else update.message
            with open(path, "rb") as photo:
                await target.reply_photo(photo=photo)
        else:
            logger.warning(f"Зображення {path} не знайдено")
    except Exception as e:
        logger.error(f"Помилка надсилання зображення {name}: {e}")


async def send_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """Надсилає текстове повідомлення"""
    target = update.callback_query.message if update.callback_query else update.message
    await target.reply_text(text, parse_mode="Markdown")


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показує головне меню з кнопками"""
    keyboard = [
        [
            InlineKeyboardButton("🎲 Випадковий факт", callback_data="random"),
            InlineKeyboardButton("🤖 Чат GPT", callback_data="gpt"),
        ],
        [
            InlineKeyboardButton("👤 Чат із зіркою", callback_data="talk"),
            InlineKeyboardButton("❓ Квіз", callback_data="quiz"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = "🔸 *Обери дію нижче:*"
    target = update.message or (update.callback_query.message if update.callback_query else None)
    if target:
        await target.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")


# ---------- КОМАНДА /start ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Старт бота"""
    context.user_data.clear()
    user = update.effective_user
    logger.info(f"Користувач {user.first_name} (ID: {user.id}) запустив бота")

    text = load_message("main")
    await send_image(update, context, "main")
    await send_text(update, context, text)
    await show_main_menu(update, context)
    return MENU


# ---------- 1. ВИПАДКОВИЙ ФАКТ ----------

async def random_fact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Генерує випадковий факт"""
    query = update.callback_query
    if query:
        await query.answer()

    await send_image(update, context, "random")

    target = update.callback_query.message if update.callback_query else update.message
    await target.reply_text("🎲 *Генерую випадковий факт...*", parse_mode="Markdown")

    prompt = load_prompt("random")
    message = "Дай мені цікавий випадковий факт"

    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(None, ask_gpt, prompt, message)

    keyboard = [
        [
            InlineKeyboardButton("🎲 Хочу ще факт", callback_data="random"),
            InlineKeyboardButton("🏠 Закінчити", callback_data="finish"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await target.reply_text(response, reply_markup=reply_markup)

    return MENU


# ---------- 2. GPT ІНТЕРФЕЙС ----------

async def gpt_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Активує режим GPT"""
    query = update.callback_query
    await query.answer()

    await send_image(update, context, "gpt")
    text = load_message("gpt")
    await send_text(update, context, text)

    return GPT_MODE


async def handle_gpt_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Режим GPT: обробка тексту користувача"""
    user_text = update.message.text
    logger.info(f"[GPT MODE] Запит: {user_text}")

    await update.message.reply_text("🔄 *Генерую відповідь...*", parse_mode="Markdown")

    prompt = "Ти дружній та корисний асистент. Відповідай українською мовою."
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(None, ask_gpt, prompt, user_text)

    await update.message.reply_text(response)
    await show_main_menu(update, context)
    return MENU


# ---------- 3. ДІАЛОГ З ВІДОМОЮ ОСОБИСТІСТЮ ----------

async def talk_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показує вибір особистостей"""
    query = update.callback_query
    await query.answer()

    await send_image(update, context, "talk")

    keyboard = [
        [InlineKeyboardButton("🎸 Курт Кобейн", callback_data="talk_cobain")],
        [InlineKeyboardButton("🚀 Ілон Маск", callback_data="talk_musk")],
        [InlineKeyboardButton("🎨 Леонардо да Вінчі", callback_data="talk_davinci")],
        [InlineKeyboardButton("🧠 Альберт Ейнштейн", callback_data="talk_einstein")],
        [InlineKeyboardButton("🏠 Закінчити", callback_data="finish")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.message.reply_text(
        "👤 *Обери відому особистість для розмови:*",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

    return TALK_MODE


async def select_personality(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Встановлює обрану особистість"""
    query = update.callback_query
    await query.answer()

    personalities = {
        "talk_cobain": ("Курт Кобейн", "cobain"),
        "talk_musk": ("Ілон Маск", "musk"),
        "talk_davinci": ("Леонардо да Вінчі", "davinci"),
        "talk_einstein": ("Альберт Ейнштейн", "einstein"),
    }

    name, prompt_file = personalities.get(query.data, ("Особистість", "default"))
    context.user_data["personality_name"] = name
    context.user_data["personality_prompt"] = load_prompt(prompt_file)

    keyboard = [[InlineKeyboardButton("🏠 Закінчити", callback_data="finish")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.message.reply_text(
        f"✅ Ти обрав розмову з *{name}*!\n\n💬 Напиши своє повідомлення:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

    return TALK_MODE


async def handle_talk_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробка повідомлень у режимі діалогу"""
    user_text = update.message.text
    prompt = context.user_data.get("personality_prompt", "Ти дружній асистент.")
    name = context.user_data.get("personality_name", "Особистість")

    logger.info(f"[TALK MODE] Розмова з {name}")

    await update.message.reply_text("🔄 *Генерую відповідь...*", parse_mode="Markdown")

    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(None, ask_gpt, prompt, user_text)

    keyboard = [[InlineKeyboardButton("🏠 Закінчити", callback_data="finish")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"*{name}:*\n{response}",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

    return TALK_MODE


# ---------- 4. КВІЗ ----------

async def quiz_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показує вибір тем квізу"""
    query = update.callback_query
    await query.answer()

    await send_image(update, context, "quiz")

    keyboard = [
        [InlineKeyboardButton("🌍 Географія", callback_data="quiz_geography")],
        [InlineKeyboardButton("🔬 Наука", callback_data="quiz_science")],
        [InlineKeyboardButton("🎬 Кіно", callback_data="quiz_cinema")],
        [InlineKeyboardButton("⚽ Спорт", callback_data="quiz_sport")],
        [InlineKeyboardButton("🏠 Закінчити", callback_data="finish")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.message.reply_text(
        "❓ *Обери тему для квізу:*",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

    return QUIZ_MODE


async def select_quiz_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Встановлює тему квізу та генерує перше питання"""
    query = update.callback_query
    await query.answer()

    topics = {
        "quiz_geography": "Географія",
        "quiz_science": "Наука",
        "quiz_cinema": "Кіно",
        "quiz_sport": "Спорт",
    }

    topic = topics.get(query.data, "Загальні знання")
    context.user_data["quiz_topic"] = topic
    context.user_data["quiz_score"] = 0
    context.user_data["quiz_total"] = 0

    await query.message.reply_text(f"✅ Обрано тему: *{topic}*\n\n🔄 *Генерую питання...*", parse_mode="Markdown")

    await generate_quiz_question(query.message, context)

    return QUIZ_MODE


async def generate_quiz_question(message, context: ContextTypes.DEFAULT_TYPE):
    """Генерує нове питання квізу"""
    topic = context.user_data.get("quiz_topic", "Загальні знання")
    prompt = f"Ти ведучий квізу. Задай одне цікаве питання з теми '{topic}'. Питання має бути середньої складності та мати конкретну відповідь. Відповідай українською."

    loop = asyncio.get_event_loop()
    question = await loop.run_in_executor(None, ask_gpt, prompt, f"Дай питання з теми {topic}")

    context.user_data["current_question"] = question
    context.user_data["waiting_for_answer"] = True

    await message.reply_text(f"❓ *Питання:*\n{question}\n\n💬 Напиши свою відповідь:", parse_mode="Markdown")


async def handle_quiz_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробка відповіді на питання квізу"""
    if not context.user_data.get("waiting_for_answer"):
        await update.message.reply_text("Спочатку обери тему квізу через /quiz")
        return QUIZ_MODE

    user_answer = update.message.text
    question = context.user_data.get("current_question", "")

    prompt = f"Ти перевіряєш відповіді на квіз. Питання: '{question}'. Відповідь користувача: '{user_answer}'. Скажи чи правильна відповідь та дай коротке пояснення українською мовою."

    await update.message.reply_text("🔄 *Перевіряю відповідь...*", parse_mode="Markdown")

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, ask_gpt, prompt, user_answer)

    # Перевіряємо чи правильна відповідь
    is_correct = any(word in result.lower() for word in ["правильно", "так", "вірно", "correct", "yes"])

    context.user_data["quiz_total"] += 1
    if is_correct:
        context.user_data["quiz_score"] += 1

    score = context.user_data["quiz_score"]
    total = context.user_data["quiz_total"]

    context.user_data["waiting_for_answer"] = False

    keyboard = [
        [InlineKeyboardButton("➡️ Наступне питання", callback_data="quiz_next")],
        [InlineKeyboardButton("🔄 Змінити тему", callback_data="quiz_change")],
        [InlineKeyboardButton("🏠 Закінчити", callback_data="finish")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"{result}\n\n📊 *Рахунок: {score}/{total}*",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

    return QUIZ_MODE


async def quiz_next_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Генерує наступне питання"""
    query = update.callback_query
    await query.answer()

    await generate_quiz_question(query.message, context)
    return QUIZ_MODE


async def quiz_change_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Повертає до вибору теми"""
    return await quiz_mode(update, context)


# ---------- ЗАГАЛЬНІ ОБРОБНИКИ ----------

async def finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Повернення до головного меню"""
    query = update.callback_query
    await query.answer()

    context.user_data.clear()
    await show_main_menu(update, context)
    return MENU


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вихід із розмови"""
    logger.info(f"Користувач вийшов із розмови")
    await update.message.reply_text("🚪 Розмову завершено. Щоб почати знову — /start")
    return ConversationHandler.END


# ---------- ЗАПУСК БОТА ----------

async def post_init(application: Application):
    """Викликається після ініціалізації бота"""
    bot_info = await application.bot.get_me()
    logger.info(f"✅ Бот підключено: @{bot_info.username} ({bot_info.first_name})")
    logger.info(f"🆔 Bot ID: {bot_info.id}")


def main():
    """Головна функція запуску бота"""
    logger.info("🚀 Запуск бота...")

    # Створюємо Application
    application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    # ConversationHandler з усіма станами
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            MENU: [
                CallbackQueryHandler(random_fact, pattern="^random$"),
                CallbackQueryHandler(gpt_mode, pattern="^gpt$"),
                CallbackQueryHandler(talk_mode, pattern="^talk$"),
                CallbackQueryHandler(quiz_mode, pattern="^quiz$"),
                CallbackQueryHandler(finish, pattern="^finish$"),
            ],
            GPT_MODE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_gpt_message),
                CallbackQueryHandler(finish, pattern="^finish$"),
            ],
            TALK_MODE: [
                CallbackQueryHandler(select_personality, pattern="^talk_"),
                CallbackQueryHandler(finish, pattern="^finish$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_talk_message),
            ],
            QUIZ_MODE: [
                CallbackQueryHandler(select_quiz_topic, pattern="^quiz_(geography|science|cinema|sport)$"),
                CallbackQueryHandler(quiz_next_question, pattern="^quiz_next$"),
                CallbackQueryHandler(quiz_change_topic, pattern="^quiz_change$"),
                CallbackQueryHandler(finish, pattern="^finish$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_quiz_answer),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)

    # Хендлер для всіх інших повідомлень (для діагностики)
    async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
        logger.info(f"📩 Отримано повідомлення від {update.effective_user.first_name}: {update.message.text}")
        await update.message.reply_text("Використай /start для початку роботи")

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    logger.info("✅ Бот запущено успішно!")
    logger.info("⏳ Чекаю на повідомлення...")

    # Запускаємо бота з обробкою помилок
    try:
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True  # Ігноруємо старі повідомлення
        )
    except Exception as e:
        logger.error(f"❌ Помилка запуску: {e}")
        raise


if __name__ == "__main__":
    main()