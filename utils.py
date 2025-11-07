"""Утиліти для роботи з ресурсами та файлами."""
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ResourceLoader:
    """Клас для завантаження ресурсів з файлів."""

    MESSAGES_DIR = "resources/messages"
    PROMPTS_DIR = "resources/prompts"
    IMAGES_DIR = "resources/images"

    DEFAULT_MESSAGES = {
        "main": "👋 *Привіт!* Я твій AI-асистент.\n\nОбери дію нижче:",
        "random": "🎲 *Випадковий факт*\n\nЗараз згенерую цікавий факт!",
        "gpt": "🤖 *ChatGPT режим*\n\nНапиши своє запитання!",
        "talk": "👤 *Діалог з особистістю*\n\nОбери з ким хочеш поговорити:",
        "quiz": "❓ *Квіз*\n\nОбери тему для питань:",
        "translate": "🌐 *Перекладач*\n\nОбери мову для перекладу:",
        "recommendations": "🎬 *Рекомендації*\n\nОбери категорію:",
    }

    DEFAULT_PROMPT = "Ти дружній асистент. Відповідай українською мовою."

    @classmethod
    def load_message(cls, name: str) -> str:
        """Завантажує текст повідомлення з файлу."""
        path = f"{cls.MESSAGES_DIR}/{name}.txt"
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except FileNotFoundError:
            logger.warning(f"Файл {path} не знайдено")
            return cls.DEFAULT_MESSAGES.get(
                name, f"Повідомлення для {name}"
            )

    @classmethod
    def load_prompt(cls, name: str) -> str:
        """Завантажує промпт з файлу."""
        path = f"{cls.PROMPTS_DIR}/{name}.txt"
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except FileNotFoundError:
            logger.error(f"Файл {path} не знайдено!")
            return cls.DEFAULT_PROMPT

    @classmethod
    def get_image_path(cls, name: str) -> Optional[str]:
        """Повертає шлях до зображення, якщо воно існує."""
        path = f"{cls.IMAGES_DIR}/{name}.jpg"
        return path if os.path.exists(path) else None

