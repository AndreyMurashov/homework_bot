import sys
import os
import time
import logging
from http import HTTPStatus

import telegram
import requests

from dotenv import load_dotenv
import exceptions
from settings import ENDPOINT, HOMEWORK_VERDICTS, RETRY_PERIOD

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    filename='homework.log',
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(stream=sys.stdout)
logger.addHandler(handler)


def log_and_raise(message, type_error):
    """Логгирует ошибки и выбрасывает исключнения"""
    logger.error(message)
    raise type_error(message)


def check_tokens():
    """Проверяет переменные окружения"""
    if not PRACTICUM_TOKEN or not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        message = 'Ошибка в переменных окружения'
        logger.critical(message)
        raise ValueError(message)
    return all(
        [
         PRACTICUM_TOKEN,
         TELEGRAM_TOKEN,
         TELEGRAM_CHAT_ID,
        ]
    )


def send_message(bot, message):
    """Отправляет сообщение"""
    try:
        logger.debug(f'Бот отправил сообщение: {message}')
        return bot.send_message(TELEGRAM_CHAT_ID, message)
    except telegram.error.TelegramError as error:
        log_and_raise(f'Боту не удалось отправить сообщение: {error}',
                      exceptions.SendMessageException)


def get_api_answer(timestamp):
    """Делает запрос к API"""
    actual_time = timestamp or int(time.time())
    parameters = {'from_date': actual_time}
    try:
        homework_verdicts = requests.get(
            ENDPOINT,
            params=parameters,
            headers=HEADERS,
        )
    except Exception as error:
        log_and_raise(f'{ENDPOINT} - Эндпойнт  недоступен: {error}',
                      exceptions.GetAPIAnswerException)
    if homework_verdicts.status_code != HTTPStatus.OK:
        log_and_raise(f'Код ответа: {homework_verdicts.status_code}',
                      exceptions.GetAPIAnswerException)
    try:
        return homework_verdicts.json()
    except Exception as error:
        log_and_raise(f'Ошибка преобразования к JSON-формату : {error}',
                      exceptions.GetAPIAnswerException)
        

def check_response(response):
    """Проверяет корректность ответа"""
    if type(response) != dict:
        log_and_raise(f'Неверный тип данных: {type(response)}',
                      TypeError)
    if 'homeworks' not in response:
        log_and_raise('homeworks - Ключ недоступен',
                      KeyError)
    homework_datas = response['homeworks']
    if type(homework_datas) != list:
        log_and_raise(f'Неверный тип данных: {type(homework_datas)}',
                      TypeError)
    return homework_datas


def parse_status(homework):
    """Извлекает статус домашней работы"""
    if 'homework_name' not in homework:
        log_and_raise('Homework_name - Ключ недоступен',
                      KeyError)
    if 'status' not in homework:
        log_and_raise('Status - Ключ недоступен',
                      KeyError)
    homework_name = homework['homework_name']
    homework_verdict = homework['status']
    if homework_verdict in HOMEWORK_VERDICTS:
        verdict = HOMEWORK_VERDICTS[homework_verdict]
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    else:
        log_and_raise('Неизвестный статус домашней работы',
                      exceptions.ParseStatusException)


def main():
    """Основная логика работы бота"""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = 1701681718 #int(time.time())
    actual_status = ''
    actual_errors = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            if not len(homework):
                logger.info('Статус не изменился')
            else:
                homework_verdict = parse_status(homework[0])
                if actual_status == homework_verdict:
                    logger.info(homework_verdict)
                else:
                    actual_status = homework_verdict
                    send_message(bot, homework_verdict)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            if actual_errors != str(error):
                actual_errors = str(error)
                send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
