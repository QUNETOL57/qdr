import os
import re
import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv('BOT_TOKEN')

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в переменных окружения!")


def parse_report(message: str) -> dict:
    result = {
        'date': None,
        'tasks': []
    }

    # Извлекаем дату из строки "Отчет о трудозатратах за ДД.ММ.ГГГГ"
    date_match = re.search(r'Отчет о трудозатратах за (\d{2}\.\d{2}\.\d{4})', message)
    if date_match:
        result['date'] = date_match.group(1)

    # Извлекаем задачи (строки начинающиеся с номера)
    # Паттерн: номер. Код задачи: описание
    task_pattern = r'\d+\.\s+([A-Z]+-\d+):\s+(.+?)(?=\n|$)'

    lines = message.split('\n')
    for i, line in enumerate(lines):
        match = re.match(task_pattern, line.strip())
        if match:
            task_code = match.group(1)
            task_description = match.group(2).strip()

            full_description = task_description

            j = i + 1
            while j < len(lines):
                next_line = lines[j].strip()
                # Если строка начинается с ⏱ или новая задача - прекращаем
                if next_line.startswith('⏱') or re.match(r'\d+\.', next_line):
                    break
                # Если строка не пустая и не является новой задачей - добавляем
                if next_line and not next_line.startswith('⏱'):
                    full_description += ' ' + next_line
                j += 1

            result['tasks'].append({
                'code': task_code,
                'description': full_description
            })

    return result


def escape_markdown(text: str) -> str:
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text


def format_report(parsed_data: dict) -> str:
    if not parsed_data['tasks']:
        return "❌ Не удалось распознать задачи в отчете\\. Проверьте формат сообщения\\."

    date_str = parsed_data['date'] if parsed_data['date'] else 'указанную дату'
    report_lines = [
        "Всем привет\\!\n",
        f"📅 Вчера \\({escape_markdown(date_str)}\\):\n"
    ]

    for task in parsed_data['tasks']:
        task_code = task['code']
        task_desc = task['description']

        url = f"https://tracker.yandex.ru/{task_code}"
        escaped_code = escape_markdown(task_code)
        escaped_desc = escape_markdown(task_desc)
        task_line = f"• T [{escaped_code}: {escaped_desc}]({url})"

        report_lines.append(task_line)

    report_lines.append("\n📅 Сегодня \\(в планах\\):\n\n• T\n• T\n• T\n• T\n• T")
    report_lines.append("\nВсем продуктивного дня\\!")

    return '\n'.join(report_lines)


async def handle_message(update: Update) -> None:
    user_message = update.message.text
    user_name = update.effective_user.first_name
    user_id = update.effective_user.id

    try:
        parsed_data = parse_report(user_message)
        response = format_report(parsed_data)
        await update.message.reply_text(response, parse_mode='MarkdownV2', disable_web_page_preview=True)
    except Exception as e:
        logger.error(f"Ошибка при обработке сообщения от {user_name} (ID: {user_id}): {e}", exc_info=True)
        await update.message.reply_text(
            "😔 Произошла ошибка при обработке вашего сообщения\\. "
            "Пожалуйста, попробуйте ещё раз или отправьте /help для справки\\.",
            parse_mode='MarkdownV2'
        )


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"Критическая ошибка: {context.error}", exc_info=context.error)

    if update and update.message:
        await update.message.reply_text(
            "😔 Произошла критическая ошибка при обработке вашего сообщения\\. "
            "Пожалуйста, попробуйте ещё раз\\.",
            parse_mode='MarkdownV2'
        )


def main() -> None:
    try:
        application = Application.builder().token(BOT_TOKEN).build()
    except Exception as e:
        logger.critical(f"Не удалось создать приложение: {e}", exc_info=True)
        raise

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.add_error_handler(error_handler)

    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        logger.critical(f"Критическая ошибка при работе бота: {e}", exc_info=True)
        raise


if __name__ == '__main__':
    main()
