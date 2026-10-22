# FILE: auditor/urls.py
"""URL routes for the repository auditor."""

from django.urls import path

from auditor import views

app_name = "auditor"
urlpatterns = [
    path("", views.home, name="home"),
    path("audit/", views.audit, name="audit"),
    path("report.json", views.export_report, name="export"),
    path("health/", views.health, name="health"),
]

# END OF FILE
# SIGNED: admin@thepandadev.com
