"""Модуль для роботи з OpenAI API."""
import logging
from openai import OpenAI
from credentials import ChatGPT_TOKEN

logger = logging.getLogger(__name__)

client = OpenAI(api_key=ChatGPT_TOKEN)


def ask_gpt(prompt: str, message: str, history: list = None) -> str:
    """
    Синхронна функція: надсилає запит до OpenAI і повертає текст відповіді.
    Викликається з bot.py через run_in_executor для асинхронної роботи.

    Args:
        prompt: Системний промпт (роль асистента)
        message: Повідомлення користувача
        history: Історія повідомлень (опціонально)

    Returns:
        Відповідь від ChatGPT
    """
    try:
        messages = [{"role": "system", "content": prompt}]
        
        # Додаємо історію, якщо вона є
        if history:
            messages.extend(history)
        
        # Додаємо поточне повідомлення
        messages.append({"role": "user", "content": message})
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.8,
        )

        answer = response.choices[0].message.content.strip()
        return answer

    except Exception as e:
        logger.error(f"Помилка GPT: {e}")
        return f"⚠️ Помилка при зверненні до ChatGPT: {e}"


def generate_random_fact(prompt: str, history_text: str = "") -> str:
    """Генерує унікальний цікавий факт."""
    message = (
        "Дай мені цікавий випадковий факт."
        f"{history_text}\n\n"
        "ВАЖЛИВО: "
        "1. Згенеруй НОВИЙ, унікальний факт, який відрізняється від попередніх. "
        "НЕ повторюй вже показані факти.\n"
        "2. Факт має бути МАКСИМУМ у 2 реченнях. НЕ більше двох речень. "
        "Будь коротким та лаконічним."
    )
    response = ask_gpt(prompt, message)
    
    # Додатково обмежуємо довжину на клієнтській стороні
    # Розділяємо на речення та беремо перші 2
    sentences = response.split('. ')
    if len(sentences) > 2:
        # Беремо перші 2 речення
        response = '. '.join(sentences[:2])
        # Додаємо крапку в кінці, якщо її немає
        if not response.endswith('.'):
            response += '.'
    
    return response


def generate_gpt_response(prompt: str, user_text: str, history: list = None) -> str:
    """Генерує відповідь GPT на запит користувача."""
    return ask_gpt(prompt, user_text, history)


def generate_talk_response(prompt: str, user_text: str, history: list = None) -> str:
    """Генерує відповідь від особистості в режимі діалогу."""
    message = (
        f"{user_text}\n\n"
        "ВАЖЛИВО: Відповідай коротко та лаконічно. "
        "Максимум 2-3 речення (не більше 150 слів). "
        "Не пиши довгі абзаци."
    )
    response = ask_gpt(prompt, message, history)

    # Обмежуємо довжину відповіді (максимум 500 символів)
    if len(response) > 500:
        truncated = response[:500]
        last_period = truncated.rfind(".")
        last_exclamation = truncated.rfind("!")
        last_question = truncated.rfind("?")
        last_sentence_end = max(
            last_period, last_exclamation, last_question
        )

        if last_sentence_end > 300:
            response = response[: last_sentence_end + 1]
        else:
            response = truncated + "..."

    return response


def generate_quiz_question(
    prompt: str, quiz_command: str, history_text: str = ""
) -> str:
    """Генерує питання для квізу."""
    message = (
        f"{quiz_command}\n\n"
        "ВАЖЛИВО: Згенеруй ТІЛЬКИ ОДНЕ питання. "
        "НЕ більше одного."
        f"{history_text}\n\n"
        "Згенеруй НОВЕ, унікальне питання, "
        "яке відрізняється від попередніх."
    )
    return ask_gpt(prompt, message)


def check_quiz_answer(
    prompt: str, question: str, user_answer: str
) -> str:
    """Перевіряє відповідь на питання квізу."""
    message = (
        f"Питання: {question}\n\n"
        f"Відповідь користувача: {user_answer}\n\n"
        "Перевір, чи відповідь правильна. "
        "Якщо правильна або дуже схожа на правильну, "
        "відповідь 'Правильно!'. "
        "Якщо неправильна, відповідь "
        "'Неправильно! Правильна відповідь - [правильна відповідь]'."
    )
    return ask_gpt(prompt, message)


def translate_text(prompt: str, text: str) -> str:
    """Перекладає текст на цільову мову."""
    return ask_gpt(prompt, text)


def generate_recommendation(
    prompt: str, category_singular: str, genre: str, is_new: bool = False
) -> str:
    """Генерує рекомендацію (фільм, книгу або музику)."""
    new_text = "новий " if is_new else ""
    message = (
        f"Дай ТІЛЬКИ ОДИН {new_text}{category_singular} у жанрі {genre}. "
        "НЕ більше одного."
    )
    return ask_gpt(prompt, message)


def extract_first_question(text: str) -> str:
    """Витягує тільки перше питання з тексту, якщо є кілька."""
    lines = text.split("\n")
    question_parts = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Якщо знайдено маркер другого питання, зупиняємося
        markers = ["2.", "2)", "2)", "Питання 2", "Question 2"]
        if any(marker in line for marker in markers):
            break

        # Якщо це не маркер першого питання, додаємо до питання
        first_markers = ["1.", "1)", "1)"]
        if not any(marker in line for marker in first_markers):
            question_parts.append(line)
        else:
            # Якщо це маркер першого питання, додаємо без маркера
            cleaned = line.lstrip("0123456789.) ")
            if cleaned:
                question_parts.append(cleaned)

    # Якщо не знайдено маркерів, беремо весь текст
    if not question_parts:
        text_clean = text.strip()
        parts = text_clean.split("\n\n")
        if parts:
            first_part = parts[0].strip()
            if len(first_part) > 200:
                sentences = first_part.split(". ")
                if sentences:
                    result = sentences[0]
                    return result + "." if not result.endswith(".") else result
            return first_part
        return text_clean[:200] if len(text_clean) > 200 else text_clean

    result = " ".join(question_parts).strip()
    # Обмежуємо довжину до розумного розміру (максимум 300 символів)
    if len(result) > 300:
        result = result[:300].rsplit(" ", 1)[0]
    return result
