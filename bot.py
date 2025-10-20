from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, ContextTypes, CommandHandler
import logging
from gpt import ChatGptService
from util import (load_message, load_prompt, send_text, send_image, show_main_menu,
                  default_callback_handler, send_text_buttons)
from credentials import ChatGPT_TOKEN, BOT_TOKEN
from telegram.error import Conflict, NetworkError


# Налаштування базового логування
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Створення екземпляру сервісу ChatGPT, використовуючи токен з середовища/облікових даних
chat_gpt = ChatGptService(ChatGPT_TOKEN)

# Створення додатку Telegram, використовуючи BOT_TOKEN з середовища/облікових даних
app = ApplicationBuilder().token(BOT_TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = load_message('main')
    await send_image(update, context, 'main')
    await send_text(update, context, text)
    await show_main_menu(update, context, {
        'start': 'Головне меню',
        'random': 'Дізнатися випадковий цікавий факт 🧠',
        'gpt': 'Задати питання чату GPT 🤖',
        'talk': 'Поговорити з відомою особистістю 👤',
        'quiz': 'Взяти участь у квізі ❓',
        # Додати команду в меню можна так:
        'command': 'button text'
    })

# Обробник команди /random для отримання випадкового факту
async def random_fact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Надсилаємо заздалегідь підготовлене зображення
    await send_image(update, context, 'random')

    # Відправляємо повідомлення про очікування відповіді від ChatGPT
    message = await send_text(update, context, "🔍 Шукаю цікавий факт для вас...")

    try:
        # Завантажуємо заздалегідь підготовлений промпт для випадкового факту
        prompt = load_prompt('random')

        # Запитуємо ChatGPT
        fact = await chat_gpt.send_question(prompt, "Розкажи мені цікавий факт")

        # Створюємо кнопки для взаємодії
        buttons = {
            'random': 'Хочу ще факт 🔄',
            'start': 'Закінчити 🏁'
        }

        # Видаляємо повідомлення про очікування
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=message.message_id)

        # Надсилаємо випадковий факт з кнопками
        await send_text_buttons(update, context, f"📚 *Випадковий факт:*\n\n{fact}", buttons)

    except Exception as e:
        logger.error(f"Помилка при отриманні випадкового факту: {e}")
        await send_text(update, context, "😔 На жаль, виникла помилка при отриманні факту. Спробуйте ще раз пізніше.")
        # Видаляємо повідомлення про очікування в разі помилки
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=message.message_id)

# Користувацький обробник колбеків для кнопок випадкових фактів
async def random_fact_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # Обов'язково відповідаємо на колбек

    # Отримуємо дані з колбеку
    data = query.data

    if data == 'random':
        # Якщо натиснуто кнопку "Хочу ще факт"
        await random_fact(update, context)
    elif data == 'start':
        # Якщо натиснуто кнопку "Закінчити"
        await start(update, context)

# Обробник помилок для бота
async def error_handler(update, context):
    logger.error(f"Помилка під час обробки оновлення: {context.error}")
    if isinstance(context.error, Conflict):
        logger.error("Конфлікт: інший екземпляр цього бота вже запущено. Переконайтесь, що працює лише один екземпляр.")
    elif isinstance(context.error, NetworkError):
        logger.error(f"Помилка мережі: {context.error}")

# Зареєструвати обробник команди можна так:
app.add_handler(CommandHandler('start', start))
app.add_handler(CommandHandler('random', random_fact))

# Зареєструвати обробник колбеку для кнопок випадкових фактів
app.add_handler(CallbackQueryHandler(random_fact_button_handler, pattern='^(random|start)$'))

# Зареєструвати обробник колбеку для інших кнопок
app.add_handler(CallbackQueryHandler(default_callback_handler))

# Додавання обробника помилок
app.add_error_handler(error_handler)

# Запуск бота з налаштуваннями для запобігання конфліктів
app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)
