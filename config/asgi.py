# FILE: config/asgi.py
"""ASGI application entry point."""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
application = get_asgi_application()

# END OF FILE
# SIGNED: admin@thepandadev.com
