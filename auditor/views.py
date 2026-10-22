# FILE: auditor/views.py
"""Views for the RepoRadar dashboard and report."""

from django.contrib import messages
from django.shortcuts import redirect, render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from auditor.services import AuditError, audit_repository, parse_repo_input


def home(request):
    """Render the landing page and optionally run an audit from a query parameter."""
    report = None
    query = request.GET.get("repo", "").strip()
    if query:
        try:
            owner, repo = parse_repo_input(query)
            report = audit_repository(owner, repo)
        except AuditError as exc:
            messages.error(request, str(exc))
    return render(request, "auditor/home.html", {"report": report, "query": query})


@require_http_methods(["POST"])
def audit(request):
    """Validate a submitted repository and redirect to a GET report URL."""
    query = request.POST.get("repo", "").strip()
    try:
        owner, repo = parse_repo_input(query)
    except AuditError as exc:
        messages.error(request, str(exc))
        return redirect("auditor:home")
    return redirect(f"/?repo={owner}/{repo}")



def health(request):
    """Lightweight health check for hosting platforms."""
    return JsonResponse({"status": "ok", "app": "RepoRadar"})

# END OF FILE
# SIGNED: admin@thepandadev.com