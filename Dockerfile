FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY . .

# Non-root runtime user
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

RUN mkdir -p uploads logs

EXPOSE 5000

# Entrypoint waits for MySQL, applies the schema, then serves via gunicorn.
CMD ["./entrypoint.sh"]
