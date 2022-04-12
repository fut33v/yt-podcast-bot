# syntax=docker/dockerfile:1

FROM python:3.9-alpine

RUN mkdir -p /home/app
RUN addgroup -S app && adduser -S app -G app
ENV HOME=/home/app
WORKDIR $HOME

RUN apk update && apk add curl

# RUN curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o /usr/local/bin/yt-dlp
# RUN chmod a+rx /usr/local/bin/yt-dlp

USER app

# COPY --chown=app . yt-podcast-bot
# WORKDIR $HOME/yt-podcast-bot
# COPY $SETTINGS_JSON barahlochannel.json

RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# how to env 
CMD ["python", "/home/app/yt-podcast-bot/bot.py"]