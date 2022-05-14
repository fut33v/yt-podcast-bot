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


class DownloadedHandlerInterface:
    def file_downloaded(self, filename: str, title:str) -> str:
        """Send downloaded file to telegram user."""
        pass


class YtPodcastDownloader:
    def __init__(self, handler: DownloadedHandlerInterface):
        self._handler = handler

    def download_video(self, url: str):
        parsed_url = urlparse(url)
        if parsed_url.path == "/watch":
            try:
                parsed_url = urlparse(url)
                video_id = parse_qs(parsed_url.query)['v'][0]
            except KeyError:
                logger.error("failed to parse url %s", url)
                return False
        else:
            video_id = parsed_url.path[1:]

        filename = video_id
        yt_dlp_process = subprocess.Popen(
            # ["yt-dlp", "-f", "140", "-o", filename, url],
            ["yt-dlp", "-f", "139", "-o", filename, url],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        yt_dlp_process.wait()
        logger.info("yt-dlp return code: %s", yt_dlp_process.returncode)

        title = None
        with YoutubeDL() as ydl:
            info_dict = ydl.extract_info(url, download=False)
            title = info_dict.get('title', None)
            # TODO: check if live
            # logger.info(info_dict)
        # logger.info("video title: %s", title)
        self._handler.file_downloaded(filename, title)



class DownloadedHandler(DownloadedHandlerInterface):
    def __init__(self, bot_token: str, chat_id: int) -> None:
        super().__init__()
        self._bot_token = bot_token
        self._chat_id = chat_id

    def file_downloaded(self, filename: str, title: str) -> str:
        bot = telegram.Bot(token=self._bot_token)
        for i in range(1, 3):
            with open(filename, "rb") as f:
                try:
                    result = bot.send_audio(chat_id=self._chat_id, audio=f, title=title, timeout=300)
                    logger.info(result)
                    break
                except telegram.error.NetworkError as e:
                    logger.error("telegram network error: %s", e)
        os.remove(filename)


class DownloaderLoop:
    def __init__(self) -> None:
        self._channel_is_open = False
        self._channel = None

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

    def _amqp_io_loop_thread(self, connection: pika.SelectConnection):
        try:
            connection.ioloop.start()
        except pika.exceptions.AMQPConnectionError:
            logger.error("failed to connect to rabbitmq!")

    def _on_connection_error(self, connection, exception):
        logger.error("failed to connect to rabbitmq!")

    def _on_connected(self, connection):
        if connection is None:
            self._channel_is_open = False
            return
        connection.channel(on_open_callback=self._on_channel_open)

    def _on_channel_open(self, channel):
        self._channel_is_open = True
        self._channel = channel

    def _on_message(self, ch, method, properties, body):
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
        except KeyError as e:
            logger.error("wrong json in to download queue %s %s", message_json, e)
            return

        handler = DownloadedHandler(bot_token=bot_token, chat_id=chat_id)
        yt_podcast_downloader = YtPodcastDownloader(handler)
        yt_podcast_downloader.download_video(url)


if __name__ == "__main__":

    loop = DownloaderLoop()
    loop.run()
