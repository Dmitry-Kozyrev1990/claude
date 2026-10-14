FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /srv/lotline

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY arttracker arttracker
COPY app app
COPY config config
COPY web/template.html web/template.html

# Демо-данные собираются при сборке образа (около 20 секунд), чтобы сервер стартовал сразу.
RUN python -m arttracker.build && rm -f data/raw_lots.jsonl data/image_embeddings.json data/truth.jsonl

RUN useradd --system --uid 1000 lotline && mkdir -p /data && chown -R lotline /data /srv/lotline/data
USER lotline
ENV LOTLINE_DB=/data/lotline.sqlite3

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
