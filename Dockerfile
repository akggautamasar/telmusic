FROM python:3.10-slim

WORKDIR /app
COPY . .

RUN apt-get update && apt-get install -y ffmpeg && \
    pip install --upgrade pip && \
    pip install -r requirements.txt

CMD ["python", "bot.py"]
