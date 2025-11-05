import logging
from openai import OpenAI
from credentials import ChatGPT_TOKEN

logger = logging.getLogger(__name__)

client = OpenAI(api_key=ChatGPT_TOKEN)


def ask_gpt(prompt: str, message: str) -> str:
    """
    Синхронна функція: надсилає запит до OpenAI і повертає текст відповіді.
    Викликається з bot.py через run_in_executor для асинхронної роботи.

    Args:
        prompt: Системний промпт (роль асистента)
        message: Повідомлення користувача

    Returns:
        Відповідь від ChatGPT
    """
    try:
        logger.info(f"Запит до GPT (перші 50 символів): {message[:50]}...")

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": message},
            ],
            temperature=0.8,
        )

        answer = response.choices[0].message.content.strip()
        logger.info(f"✅ Отримано відповідь від GPT ({len(answer)} символів)")

        return answer

    except Exception as e:
        logger.error(f"❌ Помилка GPT: {e}")
        return f"⚠️ Помилка при зверненні до ChatGPT: {e}"


if __name__ == "__main__":
    # Тестовий запуск
    print("=== ТЕСТ GPT MODULE ===\n")

    prompt = "Ти експерт з цікавих фактів. Розкажи короткий факт українською."
    message = "Розкажи факт про космос"

    print(f"Промпт: {prompt}")
    print(f"Запит: {message}\n")
    print("Відповідь GPT:")
    print(ask_gpt(prompt, message))