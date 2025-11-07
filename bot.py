"""Головний файл Telegram бота з інтеграцією ChatGPT."""
import logging
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
    BotCommand,
    BotCommandScopeDefault,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

from credentials import BOT_TOKEN
from constants import (
    MENU,
    GPT_MODE,
    TALK_MODE,
    QUIZ_MODE,
    TRANSLATE_MODE,
    RECOMMENDATIONS_MODE,
)
from utils import ResourceLoader
from handlers import (
    BaseHandler,
    RandomFactHandler,
    GPTHandler,
    TalkHandler,
    QuizHandler,
    TranslateHandler,
    RecommendationsHandler,
)

# Налаштування логування
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


class TelegramBot:
    """Головний клас для управління Telegram ботом."""

    def __init__(self, token: str):
        """Ініціалізує бота."""
        self.token = token
        self.application = None

    async def show_main_menu(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Показує головне меню з кнопками."""
        keyboard = [
            [
                InlineKeyboardButton("🎲 Цікавий факт", callback_data="random"),
                InlineKeyboardButton("🤖 Чат GPT", callback_data="gpt"),
            ],
            [
                InlineKeyboardButton("👤 Чат із зіркою", callback_data="talk"),
                InlineKeyboardButton("❓ Квіз", callback_data="quiz"),
            ],
            [
                InlineKeyboardButton("🌐 Перекладач", callback_data="translate"),
                InlineKeyboardButton("🎬 Рекомендації", callback_data="recommendations"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        text = "🔸 *Обери, що тебе цікавить:*"
        target = BaseHandler.get_target(update)
        if target:
            await target.reply_text(
                text, reply_markup=reply_markup, parse_mode="Markdown"
            )

    async def start(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Старт бота (також використовується для повернення в головне меню)."""
        query = update.callback_query
        if query:
            await query.answer()

        logger.info(
            f"Команда /start від користувача {update.effective_user.id}"
        )
        context.user_data.clear()

        await BaseHandler.send_image(update, context, "main")
        text = ResourceLoader.load_message("main")
        
        # Підставляємо ім'я користувача
        user_name = update.effective_user.first_name or "друже"
        text = text.format(name=user_name)

        target = BaseHandler.get_target(update)
        if target:
            await target.reply_text(text, parse_mode="Markdown")
        await self.show_main_menu(update, context)

        return MENU

    @staticmethod
    async def cancel(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Вихід із розмови."""
        await update.message.reply_text(
            "🚪 Розмову завершено. /start для початку"
        )
        return ConversationHandler.END

    async def post_init(self, application: Application) -> None:
        """Викликається після ініціалізації."""
        bot_info = await application.bot.get_me()
        logger.info(f"Бот запущено: @{bot_info.username}")

        commands = [
            BotCommand("start", "Головне меню"),
            BotCommand("cancel", "Скасувати поточну дію"),
        ]
        try:
            await application.bot.set_my_commands(commands)
        except Exception as e:
            logger.error(f"Помилка встановлення команд: {e}", exc_info=True)

    def _get_cross_mode_handlers(self) -> list:
        """Повертає список обробників для переходів між режимами."""
        return [
            CallbackQueryHandler(
                RandomFactHandler.handle, pattern="^random$"
            ),
            CallbackQueryHandler(
                GPTHandler.activate_mode, pattern="^gpt$"
            ),
            CallbackQueryHandler(
                TalkHandler.show_personalities, pattern="^talk$"
            ),
            CallbackQueryHandler(
                QuizHandler.show_topics, pattern="^quiz$"
            ),
            CallbackQueryHandler(
                TranslateHandler.show_languages, pattern="^translate$"
            ),
            CallbackQueryHandler(
                RecommendationsHandler.show_categories,
                pattern="^recommendations$",
            ),
        ]

    def setup_handlers(self) -> ConversationHandler:
        """Налаштовує обробники для бота."""
        cross_mode = self._get_cross_mode_handlers()
        start_button = CallbackQueryHandler(self.start, pattern="^start$")
        common = [start_button] + cross_mode
        
        return ConversationHandler(
            entry_points=[CommandHandler("start", self.start)],
            states={
                MENU: common,
                GPT_MODE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, GPTHandler.handle_message),
                    CallbackQueryHandler(GPTHandler.ask_more, pattern="^gpt_ask_more$"),
                ] + common,
                TALK_MODE: [
                    CallbackQueryHandler(TalkHandler.select_personality, pattern="^talk_"),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, TalkHandler.handle_message),
                ] + common,
                QUIZ_MODE: [
                    CallbackQueryHandler(QuizHandler.select_topic, pattern="^quiz_(geography|science|cinema|sport)$"),
                    CallbackQueryHandler(QuizHandler.next_question, pattern="^quiz_next$"),
                    CallbackQueryHandler(QuizHandler.restart, pattern="^quiz_restart$"),
                    CallbackQueryHandler(QuizHandler.change_topic, pattern="^quiz_change$"),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, QuizHandler.handle_answer),
                ] + common,
                TRANSLATE_MODE: [
                    CallbackQueryHandler(TranslateHandler.select_language, pattern="^lang_"),
                    CallbackQueryHandler(TranslateHandler.show_languages, pattern="^translate$"),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, TranslateHandler.handle_message),
                ] + common,
                RECOMMENDATIONS_MODE: [
                    CallbackQueryHandler(RecommendationsHandler.select_category, pattern="^rec_(movies|books|music)$"),
                    CallbackQueryHandler(RecommendationsHandler.select_genre, pattern="^genre_"),
                    CallbackQueryHandler(RecommendationsHandler.handle_dislike_button, pattern="^rec_dislike$"),
                ] + common,
            },
            fallbacks=[
                CommandHandler("cancel", self.cancel),
                CommandHandler("start", self.start),
            ],
        )

    def run(self) -> None:
        """Запускає бота."""
        self.application = (
            Application.builder()
            .token(self.token)
            .post_init(self.post_init)
            .build()
        )

        conv_handler = self.setup_handlers()
        self.application.add_handler(conv_handler)

        try:
            self.application.run_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True,
            )
        except KeyboardInterrupt:
            logger.info("Бот зупинено")
        except Exception as e:
            logger.error(f"Критична помилка: {e}", exc_info=True)
            raise


def main() -> None:
    """Головна функція."""
    bot = TelegramBot(BOT_TOKEN)
    bot.run()


if __name__ == "__main__":
    main()
