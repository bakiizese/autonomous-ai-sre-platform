#!/bin/sh
set -e

# Migrations run here, once per container start, rather than inside the app's
# lifespan — schema changes stay an explicit step instead of a side effect of boot.
alembic upgrade head

exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips "*"
