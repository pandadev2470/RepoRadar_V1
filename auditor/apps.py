# FILE: auditor/apps.py
"""Django application configuration."""

from django.apps import AppConfig


class AuditorConfig(AppConfig):
    """Configure the RepoRadar auditor app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "auditor"

# END OF FILE
# SIGNED: admin@thepandadev.com
