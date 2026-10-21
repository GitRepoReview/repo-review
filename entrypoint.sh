#!/bin/sh
set -e

mkdir -p "$DJANGO_DATA_DIR"
python manage.py createcachetable
python manage.py warm_cache
exec gunicorn config.wsgi \
    --workers 2 \
    --timeout 60 \
    --bind "0.0.0.0:${PORT:-8000}" \
    --access-logfile -
