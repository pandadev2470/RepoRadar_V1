# FILE: api/index.py
"""Vercel serverless entry point for Django."""

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# Vercel must provide a strong secret, external DATABASE_URL, and correct allowed hosts.
from django.core.wsgi import get_wsgi_application  # noqa: E402 - initialize path first

application = get_wsgi_application()

# END OF FILE
# SIGNED: admin@thepandadev.com
