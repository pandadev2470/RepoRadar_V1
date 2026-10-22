# FILE: config/urls.py
"""Root URL routing."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("auditor.urls")),
]

# END OF FILE
# SIGNED: admin@thepandadev.com
