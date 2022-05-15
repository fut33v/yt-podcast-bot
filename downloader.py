from ast import arg
import subprocess
from urllib.parse import urlparse
from urllib.parse import parse_qs
import logging
import pika
import time
import json
import signal
import os
import telegram
from yt_dlp import YoutubeDL
import sys
from threading import Thread, Lock

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler(sys.stdout))

AMQP_USER = os.getenv('AMQP_USER', "user")
AMQP_PASS = os.getenv('AMQP_PASS', "password")
AMQP_HOST = os.getenv('AMQP_HOST', "rabbit")


# TODO: check if live or check duration
# if too big for telegram (50 mb) separate with ffmpeg
# send messages to user

class GracefulKiller:
  kill_now = False
  def __init__(self):
    signal.signal(signal.SIGINT, self.exit_gracefully)
    signal.signal(signal.SIGTERM, self.exit_gracefully)

  def exit_gracefully(self, *args):
    self.kill_now = True


class DownloadedFile:
    def __init__(self, **kwargs) -> None:
        self.filename = kwargs['filename']
        self.title = kwargs['title']


class YtPodcastDownloader:
    def __init__(self):
        pass

    def download_video(self, url: str) -> DownloadedFile:
        parsed_url = urlparse(url)
        if parsed_url.path == "/watch":
            try:
                parsed_url = urlparse(url)
                video_id = parse_qs(parsed_url.query)['v'][0]
            except KeyError:
                logger.error("failed to parse url %s", url)
                return None
        else:
            video_id = parsed_url.path[1:]

        filename = video_id
        yt_dlp_process = subprocess.Popen(
            ["yt-dlp", "-f", "139", "-o", filename, url],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        yt_dlp_process.wait()
        with yt_dlp_process.stdout:
            for line in iter(yt_dlp_process.stdout.readline, b''):
                logger.info(line.decode("utf-8").strip())

        logger.info("yt-dlp return code: %s", yt_dlp_process.returncode)
        if yt_dlp_process.returncode != 0:
            return None

        title = None
        with YoutubeDL() as ydl:
            info_dict = ydl.extract_info(url, download=False)
            title = info_dict.get('title', None)

        return DownloadedFile(filename=filename, title=title)


class TelegramBotReplier:
    def __init__(self, bot_token, chat_id, reply_to_message_id) -> None:
        self._bot_token = bot_token
        self._chat_id = chat_id
        self._reply_to_message_id = reply_to_message_id
        pass

    def send_message(self, message):
        try:
            bot = telegram.Bot(token=self._bot_token)
            bot.send_message(chat_id=self._chat_id, text=message, reply_to_message_id=self._reply_to_message_id)
        except telegram.TelegramError as e:
            logger.error(e)

    def send_audio(self, filename: str, title: str) -> str:
        bot = telegram.Bot(token=self._bot_token)
        for i in range(1, 3):
            with open(filename, "rb") as f:
                try:
                    result = bot.send_audio(chat_id=self._chat_id, audio=f, title=title, timeout=300, reply_to_message_id=self._reply_to_message_id)
                    logger.info(result)
                    break
                except telegram.error.NetworkError as e:
                    logger.error("telegram network error: %s", e)


class DownloaderLoop:
    def __init__(self) -> None:
        self._channel_is_open = False
        self._channel = None
        self._mutex = Lock()
        self._curr_url = None
        self._curr_bot_token = None
        self._curr_chat_id = None
        self._reply_to_message_id = None

        self._threads = []

    def run(self):
        credentials = pika.PlainCredentials(AMQP_USER, AMQP_PASS)
        parameters = pika.ConnectionParameters(credentials=credentials, host=AMQP_HOST)
        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()
        channel.basic_consume(queue='to_download_queue', on_message_callback=self._on_message)
        killer = GracefulKiller()

        download_thread = Thread(target=self._downloader_thread, args=[killer])
        download_thread.start()
        while not killer.kill_now:
            try:
                channel.start_consuming()
            except KeyboardInterrupt:
                break
        channel.stop_consuming()
        connection.close()

        if self._channel_is_open and self._channel is None:
            connection.close()

        download_thread.join()

    def _downloader_thread(self, killer):
        while not killer.kill_now:
            url = None
            bot_token = None
            chat_id = None
            with self._mutex:
                url = self._curr_url
                bot_token = self._curr_bot_token
                chat_id = self._curr_chat_id
                reply_to_message_id = self._reply_to_message_id

            if url is None or bot_token is None or chat_id is None:
                time.sleep(1)
                continue

            yt_podcast_downloader = YtPodcastDownloader()
            result = yt_podcast_downloader.download_video(url)
            bot_replier = TelegramBotReplier(bot_token, chat_id, reply_to_message_id)

            if not result:
                logger.error("failed to download video")
                bot_replier.send_message("Извините, не удалось скачать данное видео.")
            else:
                bot_replier.send_audio(filename=result.filename, title=result.title)
                os.remove(result.filename)

            with self._mutex:
                self._curr_url = None
                self._curr_bot_token = None
                self._curr_chat_id = None


    def _on_message(self, channel, method, properties, body):
        try:
            message_json = json.loads(body)
        except json.JSONDecodeError:
            logger.error("failed to parse json '%s'", body)
            message_json = None
        if not message_json:
            return

        logger.info(message_json)

        try:
            url = message_json['url']
            bot_token = message_json['bot_token']
            chat_id = message_json['chat_id']
            reply_to_message_id = message_json['reply_to_message_id']
        except KeyError as e:
            logger.error("wrong json in to download queue %s %s", message_json, e)
            return

        # start thread
        t = threading.Thread

        # with self._mutex:
        #     self._curr_url = url
        #     self._curr_bot_token = bot_token
        #     self._curr_chat_id = chat_id
        #     self._reply_to_message_id = reply_to_message_id


if __name__ == "__main__":

    loop = DownloaderLoop()
    loop.run()
