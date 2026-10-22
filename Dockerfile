# FILE: Dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app
RUN pip install --no-cache-dir uv
COPY pyproject.toml README.md ./
COPY requirements.txt ./
RUN uv pip install --system -r requirements.txt
COPY . .
RUN DJANGO_DEBUG=True python manage.py collectstatic --noinput
RUN useradd --create-home app && mkdir -p /app/data && chown -R app:app /app
USER app

EXPOSE 8000
CMD ["sh", "-c", "python manage.py migrate && gunicorn config.wsgi:application --bind 0.0.0.0:${PORT} --workers 2 --timeout 90"]

# END OF FILE
# SIGNED: admin@thepandadev.com
