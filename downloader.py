# TODO: check if live or check duration
# TODO: if too big for telegram (50 mb) separate with ffmpeg

import subprocess
from urllib.parse import urlparse
from urllib.parse import parse_qs
import logging
import json
import signal
import os
import sys
import functools
from threading import Thread, Lock
from yt_dlp import YoutubeDL
import telegram
import pika

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler(sys.stdout))

AMQP_USER = os.getenv('AMQP_USER', "user")
AMQP_PASS = os.getenv('AMQP_PASS', "password")
AMQP_HOST = os.getenv('AMQP_HOST', "rabbit")


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

    def run_yt_dlp(self, filename, url, dl_format):
        yt_dlp_process = subprocess.Popen(
            ["yt-dlp", "-f", dl_format, "-o", filename, url],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        yt_dlp_process.wait()
        with yt_dlp_process.stdout:
            for line in iter(yt_dlp_process.stdout.readline, b''):
                logger.info(line.decode("utf-8").strip())
        return yt_dlp_process.returncode

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
        returncode = self.run_yt_dlp(video_id, url, "139")
        logger.info("yt-dlp -f 139 return code: %s", returncode)
        if returncode != 0:
            returncode = self.run_yt_dlp(video_id, url, "140")
            logger.info("yt-dlp -f 140 return code: %s", returncode)
            if returncode != 0:
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
        except telegram.TelegramError as error:
            logger.error(error)
            return False
        return True

    def send_audio(self, filename: str, title: str) -> str:
        with open(filename, "rb") as f:
            try:
                bot = telegram.Bot(token=self._bot_token)
                bot.send_audio(chat_id=self._chat_id, audio=f, title=title, timeout=300, reply_to_message_id=self._reply_to_message_id)
            except telegram.error.TelegramError as error:
                logger.error(error)
                return False
        return True


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

        while not killer.kill_now:
            try:
                channel.start_consuming()
            except KeyboardInterrupt:
                break
        channel.stop_consuming()
        connection.close()

        if self._channel_is_open and self._channel is None:
            connection.close()

        for t in self._threads:
            t.join()

    def _parse_download_send(self, body):
        try:
            message_json = json.loads(body)
        except json.JSONDecodeError:
            logger.error("failed to parse json '%s'", body)
            message_json = None
        if not message_json:
            return False

        logger.info(message_json)

        try:
            url = message_json['url']
            bot_token = message_json['bot_token']
            chat_id = message_json['chat_id']
            reply_to_message_id = message_json['reply_to_message_id']
        except KeyError as error:
            logger.error("wrong json in to download queue %s %s", message_json, error)
            return False

        bot_replier = TelegramBotReplier(bot_token, chat_id, reply_to_message_id)

        yt_podcast_downloader = YtPodcastDownloader()
        result = yt_podcast_downloader.download_video(url)

        if not result:
            logger.error("failed to download video")
            bot_replier.send_message("Извините, не удалось скачать данное видео.")
            return False
        else:
            filename = result.filename
            title = result.title
            ret = bot_replier.send_audio(filename=filename, title=title)
            os.remove(filename)
            if not ret:
                bot_replier.send_message("Извините, не удалось отправить данное видео.")
                return False
            return True

    def _do_work(self, ch, delivery_tag, body):
        self._parse_download_send(body)

        cb = functools.partial(self._ack_message, ch, delivery_tag)
        ch.connection.add_callback_threadsafe(cb)

    def _ack_message(self, ch, delivery_tag):
        if ch.is_open:
            ch.basic_ack(delivery_tag)
        else:
            logger.error("cant ack cause channel is already closed")

    def _on_message(self, ch, method, properties, body):
        delivery_tag = method.delivery_tag
        t = Thread(target=self._do_work, args=(ch, delivery_tag, body))
        t.start()
        self._threads.append(t)


if __name__ == "__main__":

    loop = DownloaderLoop()
    loop.run()
