FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x docker-entrypoint.sh

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://localhost:%s/' % os.environ.get('PORT', '8000'), timeout=4)"

ENTRYPOINT ["./docker-entrypoint.sh"]
