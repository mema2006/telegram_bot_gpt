"""Обробники для різних режимів бота."""
import asyncio
import logging
from functools import wraps

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from constants import (
    MENU,
    GPT_MODE,
    TALK_MODE,
    QUIZ_MODE,
    TRANSLATE_MODE,
    RECOMMENDATIONS_MODE,
)
from utils import ResourceLoader
from gpt import (
    generate_random_fact,
    generate_gpt_response,
    generate_talk_response,
    generate_quiz_question,
    check_quiz_answer,
    translate_text,
    generate_recommendation,
    extract_first_question,
)
from genres import MOVIE_GENRES, BOOK_GENRES, MUSIC_GENRES

logger = logging.getLogger(__name__)


def answer_callback_query(func):
    """Декоратор для автоматичної відповіді на callback query."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        if query:
            await query.answer()
        return await func(update, context)
    return wrapper


class BaseHandler:
    """Базовий клас для обробників."""

    @staticmethod
    async def send_image(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        name: str
    ) -> None:
        """Надсилає зображення."""
        try:
            image_path = ResourceLoader.get_image_path(name)
            if not image_path:
                logger.warning(f"Зображення {name} не знайдено")
                return

            target = (
                update.callback_query.message
                if update.callback_query
                else update.message
            )
            if target:
                with open(image_path, "rb") as photo:
                    await target.reply_photo(photo=photo)
        except Exception as e:
            logger.error(f"Помилка надсилання зображення {name}: {e}", exc_info=True)

    @staticmethod
    def escape_markdown(text: str) -> str:
        """Екранує спеціальні символи Markdown."""
        return (
            text.replace("*", "\\*")
            .replace("_", "\\_")
            .replace("[", "\\[")
            .replace("]", "\\]")
            .replace("(", "\\(")
            .replace(")", "\\)")
            .replace("`", "\\`")
        )

    @staticmethod
    def create_finish_button() -> InlineKeyboardMarkup:
        """Створює клавіатуру з кнопкою 'Закінчити'."""
        keyboard = [[InlineKeyboardButton("🏠 Закінчити", callback_data="start")]]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    async def run_gpt(func, *args):
        """Допоміжна функція для запуску GPT в executor."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, func, *args)

    @staticmethod
    def get_target(update: Update):
        """Визначає target для надсилання повідомлень."""
        return (
            update.callback_query.message
            if update.callback_query
            else update.message
        )

    @staticmethod
    def update_history(context: ContextTypes.DEFAULT_TYPE, key: str, user_text: str, response: str, max_pairs: int = 10):
        """Оновлює історію розмови."""
        history = context.user_data.get(key, [])
        history.append({"role": "user", "content": user_text})
        history.append({"role": "assistant", "content": response})
        context.user_data[key] = history[-max_pairs * 2:]  # Зберігаємо пари
        return history


class RandomFactHandler(BaseHandler):
    """Обробник для випадкових фактів."""

    @staticmethod
    async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Генерує цікавий факт."""
        query = update.callback_query
        if query:
            await query.answer()
            target = query.message
        else:
            target = update.message

        await BaseHandler.send_image(update, context, "random")
        await target.reply_text(
            "🎲 *Генерую цікавий факт...*",
            parse_mode="Markdown"
        )

        # Отримуємо історію вже показаних фактів
        facts_history = context.user_data.get("facts_history", [])

        # Формуємо повідомлення з історією фактів
        history_text = ""
        if facts_history:
            history_text = (
                "\n\nВАЖЛИВО: НЕ повторюй ці факти, які вже були показані:\n"
            )
            for i, prev_fact in enumerate(facts_history[-10:], 1):
                # Обмежуємо довжину для економії токенів
                history_text += f"{i}. {prev_fact[:100]}...\n"

        prompt = ResourceLoader.load_prompt("random")
        response = await BaseHandler.run_gpt(
            generate_random_fact, prompt, history_text
        )

        # Додаємо факт до історії
        facts_history.append(response)
        context.user_data["facts_history"] = facts_history[-20:]  # Зберігаємо останні 20 фактів

        keyboard = [
            [
                InlineKeyboardButton(
                    "🎲 Хочу ще факт", callback_data="random"
                ),
                InlineKeyboardButton("📤 Поділитися", switch_inline_query=response[:100]),
            ],
            [
                InlineKeyboardButton("🏠 Закінчити", callback_data="start"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await target.reply_text(response, reply_markup=reply_markup)

        return MENU


class GPTHandler(BaseHandler):
    """Обробник для GPT режиму."""

    @staticmethod
    async def activate_mode(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Активує режим GPT."""
        query = update.callback_query
        if query:
            await query.answer()
            await BaseHandler.send_image(update, context, "gpt")
            text = ResourceLoader.load_message("gpt")
            await query.message.reply_text(
                text,
                reply_markup=BaseHandler.create_finish_button(),
                parse_mode="Markdown"
            )

        return GPT_MODE

    @staticmethod
    async def handle_message(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Обробка повідомлення в GPT режимі."""
        user_text = update.message.text

        await update.message.reply_text(
            "🔄 *Генерую відповідь...*", parse_mode="Markdown"
        )

        history = context.user_data.get("gpt_history", [])
        prompt = ResourceLoader.load_prompt("gpt")
        response = await BaseHandler.run_gpt(
            generate_gpt_response, prompt, user_text, history
        )
        BaseHandler.update_history(context, "gpt_history", user_text, response)

        keyboard = [
            [
                InlineKeyboardButton(
                    "💬 Запитати ще", callback_data="gpt_ask_more"
                ),
                InlineKeyboardButton("🏠 Закінчити", callback_data="start"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(response, reply_markup=reply_markup)

        return GPT_MODE

    @staticmethod
    async def ask_more(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Продовжує режим GPT для нового запиту."""
        query = update.callback_query
        if query:
            await query.answer()
            # Очищуємо історію для нової розмови
            context.user_data["gpt_history"] = []
            text = ResourceLoader.load_message("gpt")
            await query.message.reply_text(
                text,
                reply_markup=BaseHandler.create_finish_button(),
                parse_mode="Markdown"
            )

        return GPT_MODE


class TalkHandler(BaseHandler):
    """Обробник для діалогу з особистостями."""

    PERSONALITIES = {
        "talk_cobain": ("Курт Кобейн", "talk_cobain"),
        "talk_queen": ("Єлизавета II", "talk_queen"),
        "talk_tolkien": ("Джон Толкін", "talk_tolkien"),
        "talk_nietzsche": ("Фрідріх Ніцше", "talk_nietzsche"),
        "talk_hawking": ("Стівен Гокінг", "talk_hawking"),
    }

    @staticmethod
    async def show_personalities(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Показує вибір особистостей."""
        query = update.callback_query
        if not query:
            logger.error("talk_mode: query is None")
            return TALK_MODE

        await query.answer()
        await BaseHandler.send_image(update, context, "talk")

        keyboard = [
            [
                InlineKeyboardButton(
                    "🎸 Курт Кобейн", callback_data="talk_cobain"
                )
            ],
            [
                InlineKeyboardButton(
                    "👑 Єлизавета II", callback_data="talk_queen"
                )
            ],
            [
                InlineKeyboardButton(
                    "📖 Джон Толкін", callback_data="talk_tolkien"
                )
            ],
            [
                InlineKeyboardButton(
                    "🧠 Фрідріх Ніцше", callback_data="talk_nietzsche"
                )
            ],
            [
                InlineKeyboardButton(
                    "🔬 Стівен Гокінг", callback_data="talk_hawking"
                )
            ],
            [
                InlineKeyboardButton(
                    "🏠 Закінчити", callback_data="finish"
                )
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        text = ResourceLoader.load_message("talk")
        await query.message.reply_text(
            text, reply_markup=reply_markup, parse_mode="Markdown"
        )

        return TALK_MODE

    @staticmethod
    async def select_personality(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Встановлює обрану особистість."""
        query = update.callback_query
        if not query:
            logger.error("select_personality: query is None")
            return TALK_MODE

        await query.answer()

        name, prompt_file = TalkHandler.PERSONALITIES.get(
            query.data, ("Особистість", "default")
        )
        context.user_data["personality_name"] = name
        context.user_data["personality_prompt"] = (
            ResourceLoader.load_prompt(prompt_file)
        )
        # Очищуємо історію для нової особистості
        context.user_data["talk_history"] = []

        # Завантажуємо фото зірки
        image_path = ResourceLoader.get_image_path(prompt_file)
        if image_path:
            try:
                with open(image_path, "rb") as photo:
                    await query.message.reply_photo(photo=photo)
            except Exception as e:
                logger.error(f"Помилка надсилання фото {name}: {e}", exc_info=True)
        else:
            logger.warning(f"Фото не знайдено: {prompt_file}")

        await query.message.reply_text(
            f"✅ Розмова з *{name}*!\n\n💬 Напиши своє повідомлення:",
            reply_markup=BaseHandler.create_finish_button(),
            parse_mode="Markdown"
        )

        return TALK_MODE

    @staticmethod
    async def handle_message(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Обробка повідомлень у режимі діалогу."""
        user_text = update.message.text
        prompt = context.user_data.get(
            "personality_prompt",
            ResourceLoader.load_prompt("default")
        )
        name = context.user_data.get("personality_name", "Особистість")

        await update.message.reply_text(
            "🔄 *Генерую відповідь...*", parse_mode="Markdown"
        )

        history = context.user_data.get("talk_history", [])
        response = await BaseHandler.run_gpt(
            generate_talk_response, prompt, user_text, history
        )
        BaseHandler.update_history(context, "talk_history", user_text, response)

        await update.message.reply_text(
            f"*{name}:*\n{response}",
            reply_markup=BaseHandler.create_finish_button(),
            parse_mode="Markdown"
        )

        return TALK_MODE


class QuizHandler(BaseHandler):
    """Обробник для квізу."""

    TOPICS = {
        "quiz_geography": ("Географія", "quiz_geography"),
        "quiz_science": ("Наука", "quiz_science"),
        "quiz_cinema": ("Кіно", "quiz_cinema"),
        "quiz_sport": ("Спорт", "quiz_sport"),
    }

    @staticmethod
    @answer_callback_query
    async def show_topics(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Показує вибір тем квізу."""
        query = update.callback_query

        await BaseHandler.send_image(update, context, "quiz")

        keyboard = [
            [
                InlineKeyboardButton(
                    "🌍 Географія", callback_data="quiz_geography"
                )
            ],
            [
                InlineKeyboardButton(
                    "🔬 Наука", callback_data="quiz_science"
                )
            ],
            [
                InlineKeyboardButton(
                    "🎬 Кіно", callback_data="quiz_cinema"
                )
            ],
            [
                InlineKeyboardButton(
                    "⚽ Спорт", callback_data="quiz_sport"
                )
            ],
            [
                InlineKeyboardButton(
                    "🏠 Закінчити", callback_data="finish"
                )
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.message.reply_text(
            "❓ *Обери тему для квізу:*",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

        return QUIZ_MODE

    @staticmethod
    @answer_callback_query
    async def select_topic(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Встановлює тему квізу та генерує перше питання."""
        query = update.callback_query

        topic_name, quiz_command = QuizHandler.TOPICS.get(
            query.data, ("Загальні знання", "quiz_biology")
        )
        context.user_data["quiz_topic"] = topic_name
        context.user_data["quiz_command"] = quiz_command
        context.user_data["quiz_original_command"] = quiz_command
        context.user_data["quiz_score"] = 0
        context.user_data["quiz_total"] = 0
        context.user_data["quiz_questions_history"] = []

        await query.message.reply_text(
            f"✅ Обрано тему: *{topic_name}*\n\n🔄 *Генерую питання...*",
            parse_mode="Markdown"
        )

        await QuizHandler.generate_question(query.message, context)

        return QUIZ_MODE

    @staticmethod
    async def generate_question(
        message, context: ContextTypes.DEFAULT_TYPE
    ):
        """Генерує нове питання квізу."""
        quiz_command = context.user_data.get("quiz_command", "quiz_biology")
        prompt = ResourceLoader.load_prompt("quiz")

        questions_history = context.user_data.get(
            "quiz_questions_history", []
        )

        history_text = ""
        if questions_history:
            history_text = (
                "\n\nВАЖЛИВО: НЕ повторюй ці питання, "
                "які вже були задані:\n"
            )
            for i, prev_question in enumerate(questions_history[-5:], 1):
                history_text += f"{i}. {prev_question[:100]}...\n"

        question_raw = await BaseHandler.run_gpt(
            generate_quiz_question, prompt, quiz_command, history_text
        )

        question = extract_first_question(question_raw)

        questions_history.append(question)
        context.user_data["quiz_questions_history"] = (
            questions_history[-10:]
        )

        context.user_data["current_question"] = question
        context.user_data["waiting_for_answer"] = True

        question_escaped = BaseHandler.escape_markdown(question)

        try:
            await message.reply_text(
                f"❓ *Питання:*\n{question_escaped}\n\n"
                f"💬 Напиши свою відповідь:",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Помилка парсингу Markdown: {e}")
            await message.reply_text(
                f"❓ Питання:\n{question}\n\n💬 Напиши свою відповідь:"
            )

    @staticmethod
    async def handle_answer(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Обробка відповіді на питання квізу."""
        if not context.user_data.get("waiting_for_answer"):
            await update.message.reply_text("Спочатку обери тему квізу!")
            return QUIZ_MODE

        user_answer = update.message.text
        current_question = context.user_data.get("current_question", "")
        prompt = ResourceLoader.load_prompt("quiz")

        await update.message.reply_text(
            "🔄 *Перевіряю відповідь...*", parse_mode="Markdown"
        )

        result = await BaseHandler.run_gpt(
            check_quiz_answer, prompt, current_question, user_answer
        )

        result_lower = result.lower().strip()
        is_correct = False

        if result_lower.startswith("неправильно"):
            is_correct = False
        elif (
            result_lower.startswith("правильно")
            or "правильно!" in result_lower
        ):
            is_correct = True
        elif any(word in result_lower for word in ["так", "вірно", "correct"]):
            is_correct = True

        context.user_data["quiz_total"] = (
            context.user_data.get("quiz_total", 0) + 1
        )

        if is_correct:
            context.user_data["quiz_score"] = (
                context.user_data.get("quiz_score", 0) + 1
            )

        score = context.user_data.get("quiz_score", 0)
        total = context.user_data.get("quiz_total", 0)
        context.user_data["waiting_for_answer"] = False

        keyboard = [
            [
                InlineKeyboardButton(
                    "➡️ Наступне питання", callback_data="quiz_next"
                )
            ],
            [
                InlineKeyboardButton(
                    "🔄 Почати спочатку", callback_data="quiz_restart"
                )
            ],
            [
                InlineKeyboardButton(
                    "🔄 Змінити тему", callback_data="quiz_change"
                )
            ],
            [
                InlineKeyboardButton(
                    "🏠 Закінчити", callback_data="finish"
                )
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        result_escaped = BaseHandler.escape_markdown(result)

        score_text = (
            f"📊 *Правильних відповідей: {score} з {total}*"
            if total > 0
            else "📊 *Рахунок: 0/0*"
        )

        try:
            await update.message.reply_text(
                f"{result_escaped}\n\n{score_text}",
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Помилка парсингу Markdown: {e}")
            score_text_plain = (
                f"📊 Правильних відповідей: {score} з {total}"
                if total > 0
                else "📊 Рахунок: 0/0"
            )
            await update.message.reply_text(
                f"{result}\n\n{score_text_plain}",
                reply_markup=reply_markup
            )

        return QUIZ_MODE

    @staticmethod
    async def next_question(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Генерує наступне питання."""
        query = update.callback_query
        if query:
            await query.answer()
            original_command = context.user_data.get(
                "quiz_original_command", "quiz_biology"
            )
            context.user_data["quiz_command"] = original_command
            await QuizHandler.generate_question(query.message, context)

        return QUIZ_MODE

    @staticmethod
    async def restart(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Починає гру спочатку (обнуляє рахунок)."""
        query = update.callback_query
        if query:
            await query.answer()

        context.user_data["quiz_score"] = 0
        context.user_data["quiz_total"] = 0
        context.user_data["waiting_for_answer"] = False
        context.user_data["quiz_questions_history"] = []

        original_command = context.user_data.get(
            "quiz_original_command", "quiz_biology"
        )
        context.user_data["quiz_command"] = original_command

        await query.message.reply_text(
            "🔄 *Рахунок обнулено! Генерую нове питання...*",
            parse_mode="Markdown"
        )

        await QuizHandler.generate_question(query.message, context)

        return QUIZ_MODE

    @staticmethod
    async def change_topic(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Повертає до вибору теми."""
        context.user_data["quiz_score"] = 0
        context.user_data["quiz_total"] = 0
        context.user_data["waiting_for_answer"] = False
        context.user_data["quiz_questions_history"] = []
        return await QuizHandler.show_topics(update, context)


class TranslateHandler(BaseHandler):
    """Обробник для перекладача."""

    LANGUAGES = {
        "lang_en": "англійську",
        "lang_de": "німецьку",
        "lang_fr": "французьку",
        "lang_es": "іспанську",
        "lang_pl": "польську",
        "lang_ru": "російську",
    }

    @staticmethod
    @answer_callback_query
    async def show_languages(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Показує вибір мови для перекладу."""
        query = update.callback_query

        await BaseHandler.send_image(update, context, "translate")

        keyboard = [
            [
                InlineKeyboardButton(
                    "🇬🇧 Англійська", callback_data="lang_en"
                ),
                InlineKeyboardButton(
                    "🇩🇪 Німецька", callback_data="lang_de"
                ),
            ],
            [
                InlineKeyboardButton(
                    "🇫🇷 Французька", callback_data="lang_fr"
                ),
                InlineKeyboardButton(
                    "🇪🇸 Іспанська", callback_data="lang_es"
                ),
            ],
            [
                InlineKeyboardButton(
                    "🇵🇱 Польська", callback_data="lang_pl"
                ),
                InlineKeyboardButton(
                    "🇷🇺 Російська", callback_data="lang_ru"
                ),
            ],
            [
                InlineKeyboardButton(
                    "🏠 Закінчити", callback_data="finish"
                )
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.message.reply_text(
            "🌐 *Обери мову для перекладу:*",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

        return TRANSLATE_MODE

    @staticmethod
    @answer_callback_query
    async def select_language(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Встановлює обрану мову."""
        query = update.callback_query

        lang_name = TranslateHandler.LANGUAGES.get(
            query.data, "обрану"
        )
        context.user_data["target_language"] = lang_name

        keyboard = [
            [InlineKeyboardButton("🔄 Змінити мову", callback_data="translate")],
            [InlineKeyboardButton("🏠 Закінчити", callback_data="finish")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(
            f"✅ Обрано: *{lang_name}*\n\n💬 Напиши текст для перекладу:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

        return TRANSLATE_MODE

    @staticmethod
    async def handle_message(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Обробка тексту для перекладу."""
        if "target_language" not in context.user_data:
            await update.message.reply_text("Спочатку обери мову!")
            return TRANSLATE_MODE

        user_text = update.message.text
        lang_name = context.user_data["target_language"]

        await update.message.reply_text(
            "🔄 *Перекладаю...*", parse_mode="Markdown"
        )

        prompt = ResourceLoader.load_prompt("translate").format(lang_name=lang_name)
        translation = await BaseHandler.run_gpt(translate_text, prompt, user_text)

        keyboard = [
            [
                InlineKeyboardButton(
                    "🔄 Змінити мову", callback_data="translate"
                )
            ],
            [
                InlineKeyboardButton(
                    "🏠 Закінчити", callback_data="finish"
                )
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"📝 *Переклад:*\n{translation}",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

        return TRANSLATE_MODE


class RecommendationsHandler(BaseHandler):
    """Обробник для рекомендацій."""

    CATEGORIES = {
        "rec_movies": "фільми",
        "rec_books": "книги",
        "rec_music": "музику",
    }

    CATEGORY_SINGULAR = {
        "фільми": "фільм",
        "книги": "книгу",
        "музику": "музичний твір",
    }

    GENRES = {
        "фільми": MOVIE_GENRES,
        "книги": BOOK_GENRES,
        "музику": MUSIC_GENRES,
    }

    @staticmethod
    @answer_callback_query
    async def show_categories(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Показує вибір категорії."""
        query = update.callback_query

        if "disliked_items" not in context.user_data:
            context.user_data["disliked_items"] = []

        await BaseHandler.send_image(update, context, "recommendations")

        keyboard = [
            [
                InlineKeyboardButton(
                    "🎬 Фільми", callback_data="rec_movies"
                )
            ],
            [
                InlineKeyboardButton(
                    "📚 Книги", callback_data="rec_books"
                )
            ],
            [
                InlineKeyboardButton(
                    "🎵 Музика", callback_data="rec_music"
                )
            ],
            [
                InlineKeyboardButton(
                    "🏠 Закінчити", callback_data="finish"
                )
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.message.reply_text(
            "🎬 *Обери категорію:*",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

        return RECOMMENDATIONS_MODE

    @staticmethod
    @answer_callback_query
    async def select_category(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Встановлює категорію та показує жанри."""
        query = update.callback_query

        category = RecommendationsHandler.CATEGORIES.get(
            query.data, "фільми"
        )
        context.user_data["recommendation_category"] = category

        # Визначаємо жанри та емодзі залежно від категорії
        genres = RecommendationsHandler.GENRES.get(category, MOVIE_GENRES)
        category_emoji = {"фільми": "🎬", "книги": "📚", "музику": "🎵"}.get(
            category, "🎬"
        )

        # Створюємо кнопки з жанрами (по 2 в рядку)
        keyboard = []
        genre_items = list(genres.items())
        for i in range(0, len(genre_items), 2):
            row = []
            row.append(
                InlineKeyboardButton(
                    genre_items[i][1], callback_data=genre_items[i][0]
                )
            )
            if i + 1 < len(genre_items):
                row.append(
                    InlineKeyboardButton(
                        genre_items[i + 1][1],
                        callback_data=genre_items[i + 1][0],
                    )
                )
            keyboard.append(row)

        keyboard.append(
            [
                InlineKeyboardButton(
                    "🏠 Закінчити", callback_data="finish"
                )
            ]
        )
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.message.reply_text(
            f"✅ Категорія: *{category}*\n\n{category_emoji} *Обери жанр:*",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

        return RECOMMENDATIONS_MODE

    @staticmethod
    @answer_callback_query
    async def select_genre(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Обробка вибору жанру через кнопку."""
        query = update.callback_query

        if "recommendation_category" not in context.user_data:
            await query.message.reply_text("Спочатку обери категорію!")
            return RECOMMENDATIONS_MODE

        category = context.user_data["recommendation_category"]

        # Визначаємо словник жанрів залежно від категорії
        genres = RecommendationsHandler.GENRES.get(category, MOVIE_GENRES)
        genre = genres.get(query.data, "загальний")
        
        # Викликаємо генерацію рекомендації з обраним жанром
        return await RecommendationsHandler.generate_recommendation(
            query.message, context, genre
        )

    @staticmethod
    async def generate_recommendation(
        message, context: ContextTypes.DEFAULT_TYPE, genre: str
    ):
        """Генерує рекомендацію для обраного жанру."""
        category = context.user_data.get("recommendation_category", "фільми")
        disliked_items = context.user_data.get("disliked_items", [])

        context.user_data["last_genre"] = genre

        await message.reply_text(
            "🔄 *Генерую рекомендацію...*", parse_mode="Markdown"
        )

        # Формуємо промпт
        disliked_text = ""
        if disliked_items:
            disliked_text = f"\n\nНе рекомендуй: {', '.join(disliked_items)}."

        category_singular = RecommendationsHandler.CATEGORY_SINGULAR.get(
            category, category
        )

        # Додаємо інструкцію про рейтинг для фільмів
        rating_instruction = ""
        if category == "фільми":
            rating_instruction = ResourceLoader.load_prompt("rating_instruction")

        prompt = ResourceLoader.load_prompt("recommendations").format(
            category=category,
            category_singular=category_singular,
            genre=genre,
            rating_instruction=rating_instruction
        ) + disliked_text

        recommendations = await BaseHandler.run_gpt(
            generate_recommendation, prompt, category_singular, genre
        )

        context.user_data["waiting_for_dislike"] = True
        context.user_data["waiting_for_dislike_input"] = False

        keyboard = [
            [
                InlineKeyboardButton(
                    "👎 Не подобається", callback_data="rec_dislike"
                ),
                InlineKeyboardButton(
                    "📤 Поділитися", switch_inline_query=recommendations[:100]
                ),
            ],
            [
                InlineKeyboardButton(
                    "🏠 Закінчити", callback_data="finish"
                )
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Зберігаємо останню рекомендацію для автоматичного витягування назви
        context.user_data["last_recommendation"] = recommendations

        await message.reply_text(
            f"📋 *Рекомендація ({category}):*\n\n{recommendations}",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

        return RECOMMENDATIONS_MODE

    @staticmethod
    def extract_title_from_recommendation(recommendation_text: str) -> str:
        """Витягує назву твору з тексту рекомендації."""
        # Шукаємо рядок, що починається з "Назва:" або "Назва твору:"
        lines = recommendation_text.split("\n")
        for line in lines:
            line = line.strip()
            if line.startswith("Назва:") or line.startswith("Назва твору:"):
                # Витягуємо текст після "Назва:"
                title = line.split(":", 1)[1].strip()
                # Прибираємо можливі markdown символи
                title = title.replace("*", "").replace("_", "").strip()
                return title
        
        # Якщо не знайдено "Назва:", беремо перший рядок (зазвичай там назва)
        if lines:
            first_line = lines[0].strip()
            # Прибираємо markdown та обмежуємо довжину
            first_line = first_line.replace("*", "").replace("_", "").strip()
            # Обмежуємо до 100 символів
            if len(first_line) > 100:
                first_line = first_line[:100].rsplit(" ", 1)[0]
            return first_line
        
        return "Невідомий твір"

    @staticmethod
    @answer_callback_query
    async def handle_dislike_button(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Обробка кнопки 'Не подобається'."""
        query = update.callback_query

        if not context.user_data.get("waiting_for_dislike"):
            await query.message.reply_text("Спочатку отримай рекомендації")
            return RECOMMENDATIONS_MODE

        # Автоматично витягуємо назву з останньої рекомендації
        last_recommendation = context.user_data.get("last_recommendation", "")
        if not last_recommendation:
            await query.message.reply_text(
                "Не вдалося знайти останню рекомендацію"
            )
            return RECOMMENDATIONS_MODE

        disliked_item = RecommendationsHandler.extract_title_from_recommendation(
            last_recommendation
        )
        disliked_items = context.user_data.get("disliked_items", [])

        if disliked_item not in disliked_items:
            disliked_items.append(disliked_item)
            context.user_data["disliked_items"] = disliked_items

        context.user_data["waiting_for_dislike"] = False
        context.user_data["waiting_for_dislike_input"] = False

        category = context.user_data.get("recommendation_category", "фільми")
        genre = context.user_data.get("last_genre", "загальний")

        await query.message.reply_text(
            f"✅ Додано до списку небажаних: *{disliked_item}*\n\n"
            "🔄 *Генерую нову рекомендацію...*",
            parse_mode="Markdown"
        )

        # Генеруємо нову рекомендацію
        return await RecommendationsHandler.generate_recommendation(
            query.message, context, genre
        )

