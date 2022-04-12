import os

import telegram.ext
from telegram.ext import Updater, CommandHandler


def start_handler(update, context):
    message_text = """
С помощью этого бота можно скачать звуковую дорожку из ютуб видео.
*Техподдержка:* @fut33v
"""

    context.bot.send_message(chat_id=update.effective_chat.id,
                             text=message_text,
                             parse_mode=telegram.ParseMode.MARKDOWN)


if __name__ == "__main__":

    token_telegram = os.getenv("BOT_TOKEN", None)
    if token_telegram is None:
        print("bot token not found in env!")
        exit(-1)

    updater = Updater(token_telegram, use_context=True)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler('start', start_handler))
    # dispatcher.add_error_handler(error)

    updater.start_polling()
    updater.idle()


# yt-dlp -f 140 https://www.youtube.com/watch\?v\=h5pc2zA5enA