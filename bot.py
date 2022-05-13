import logging
import os
import telegram
import telegram.ext
from telegram.ext import Updater, CommandHandler, MessageHandler, filters
import pika
import json
import sys

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler(sys.stdout))

AMQP_USER = os.getenv('AMQP_USER', "user")
AMQP_PASS = os.getenv('AMQP_PASS', "password")
AMQP_HOST = os.getenv('AMQP_HOST', "rabbit")
BOT_TOKEN = os.getenv('BOT_TOKEN', None)


def start_handler(update, context):
    message_text = """
С помощью этого бота можно скачать звуковую дорожку из ютуб видео.
*Техподдержка:* @fut33v
"""
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text=message_text,
                             parse_mode=telegram.ParseMode.MARKDOWN)


def url_handler(update: telegram.Update, context):
    logger.info(update.effective_message)
    credentials = pika.PlainCredentials(AMQP_USER, AMQP_PASS)
    parameters = pika.ConnectionParameters(credentials=credentials, host=AMQP_HOST)
    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()
    message = json.dumps({"url": update.effective_message.text, "chat_id": update.effective_chat.id, "bot_token": BOT_TOKEN})
    channel.basic_publish('', 'to_download_queue', message,
        pika.BasicProperties(content_type='text/plain', type='example'))
    connection.close()


if __name__ == "__main__":

    token_telegram = BOT_TOKEN
    if token_telegram is None:
        print("bot token not found in env!")
        exit(-1)

    updater = Updater(token_telegram, use_context=True)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler('start', start_handler))
    dispatcher.add_handler(MessageHandler(filters=filters.Filters.entity('url'), callback=url_handler))
    # dispatcher.add_error_handler(error)

    updater.start_polling()
    updater.idle()

