import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
# The SQLite file (DB and report cache) lives here; in the image it is a mounted volume.
DATA_DIR = Path(os.environ.get("DJANGO_DATA_DIR", BASE_DIR))

DEBUG = os.environ.get("DJANGO_DEBUG") == "1"
SECRET_KEY = "dev-only-insecure-key" if DEBUG else os.environ["DJANGO_SECRET_KEY"]
ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "*" if DEBUG else "").split(",")
    if h.strip()
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
]

# The built SPA is served by WhiteNoise from the site root; Django only handles /api/.
FRONTEND_DIST = os.environ.get("DJANGO_FRONTEND_DIST")
if FRONTEND_DIST:
    WHITENOISE_ROOT = FRONTEND_DIST
    WHITENOISE_INDEX_FILE = True

INSTALLED_APPS = ["analysis"]
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

# No models yet; the DB is only here because Django requires one to be configured.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DATA_DIR / "db.sqlite3",
    }
}

USE_TZ = True

# Reports are cached in a table of the same SQLite file. Create it with
# `manage.py createcachetable` (compose does this at startup).
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "report_cache",
    }
}
