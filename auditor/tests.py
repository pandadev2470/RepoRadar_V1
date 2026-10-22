# FILE: auditor/tests.py
"""Tests for repository input validation and report scoring."""

from unittest.mock import patch

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from auditor.services import AuditError, parse_repo_input


class ParseRepoInputTests(SimpleTestCase):
    """Validate accepted GitHub repository input formats."""

    def test_owner_repo_format(self):
        self.assertEqual(parse_repo_input("django/django"), ("django", "django"))

    def test_github_url_and_git_suffix(self):
        self.assertEqual(parse_repo_input("https://github.com/pallets/flask.git"), ("pallets", "flask"))

    def test_rejects_other_domains(self):
        with self.assertRaises(AuditError):
            parse_repo_input("https://example.com/owner/repo")

    def test_rejects_missing_repository(self):
        with self.assertRaises(AuditError):
            parse_repo_input("owner")


class HomeViewTests(TestCase):
    """Check basic landing page and input error handling."""

    def test_home_page_loads(self):
        response = self.client.get(reverse("auditor:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "RepoRadar")

    def test_invalid_submission_redirects(self):
        response = self.client.post(reverse("auditor:audit"), {"repo": "not-a-repo"})
        self.assertEqual(response.status_code, 302)


# END OF FILE
# SIGNED: admin@thepandadev.com
