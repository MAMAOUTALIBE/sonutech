FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home app
COPY --chown=app:app . .
RUN mkdir -p /app/media /app/staticfiles && chown -R app:app /app/media /app/staticfiles
USER app
EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "45", "--access-logfile", "-", "--access-logformat", "%(m)s %(U)s %(s)s %(L)s"]
