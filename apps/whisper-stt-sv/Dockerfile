FROM python:3.12.11-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 whisper \
    && mkdir -p /home/whisper/.cache/huggingface \
    && chown -R whisper:whisper /home/whisper

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server.py .
RUN chown whisper:whisper /app/server.py

ENV HOME=/home/whisper
ENV HF_HOME=/home/whisper/.cache/huggingface
USER whisper

EXPOSE 9000
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:9000/health')"

CMD ["python", "-u", "server.py"]
