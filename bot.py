import os

import telegram.ext
from telegram.ext import Updater, CommandHandler
from yt_dlp import YoutubeDL

def start_handler(update, context):
    message_text = """
С помощью этого бота можно скачать звуковую дорожку из ютуб видео.
*Техподдержка:* @fut33v
"""

    context.bot.send_message(chat_id=update.effective_chat.id,
                             text=message_text,
                             parse_mode=telegram.ParseMode.MARKDOWN)



# yt-dlp -f 140 https://www.youtube.com/watch\?v\=h5pc2zA5enA
def download_video(url: str):
    # ydl_opts = {'format': 'bestaudio'}
    # ydl_opts = {
    #     '-f': 'ba',
    #     '-x': True,
    #     '--audio-format': 'mp3'
    # }
    # ydl_opts = {'format': 'bestaudio'}
    ydl_opts = {'format': '140'}
    with YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

# yt-dlp -f 140 -o "vtech.%(ext)s" -x --audio-format mp3 https://www.youtube.com/watch\?v\=gFT0BDIDFUg

if __name__ == "__main__":

    test_video = "https://www.youtube.com/watch?v=P1qBe_TIXhM"
    download_video(test_video)
    exit(0)

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

