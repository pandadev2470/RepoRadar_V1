# FILE: auditor/tests.py
"""Tests for repository input validation and report scoring."""

from unittest.mock import patch

import httpx
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from auditor.services import AuditError, _get_json, audit_repository, parse_repo_input


class ParseRepoInputTests(SimpleTestCase):
    """Validate accepted GitHub repository input formats."""

    def test_owner_repo_format(self):
        self.assertEqual(parse_repo_input("django/django"), ("django", "django"))

    def test_github_url_and_git_suffix(self):
        self.assertEqual(
            parse_repo_input("https://github.com/pallets/flask.git"), ("pallets", "flask")
        )

    def test_rejects_other_domains(self):
        with self.assertRaises(AuditError):
            parse_repo_input("https://example.com/owner/repo")

    def test_rejects_missing_repository(self):
        with self.assertRaises(AuditError):
            parse_repo_input("owner")


@override_settings(
    STORAGES={"staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}}
)
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


class ServiceRegressionTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def test_schemeless_url(self):
        self.assertEqual(parse_repo_input("github.com/django/django"), ("django", "django"))

    def test_invalid_inputs(self):
        for value in [
            "a/b/c",
            "https://github.com:bad/a/b",
            "https://user@github.com/a/b",
            "ftp://github.com/a/b",
            "a/..",
            "x" * 301,
        ]:
            with self.subTest(value=value), self.assertRaises(AuditError):
                parse_repo_input(value)

    def test_transport_and_response_errors(self):
        for response in [
            httpx.Response(200, content=b"not json"),
            httpx.Response(200, json=[]),
            httpx.Response(302),
            httpx.Response(429),
            httpx.Response(200, content=b"x" * 1000001),
        ]:
            with self.subTest(status=response.status_code):
                with httpx.Client(
                    transport=httpx.MockTransport(lambda request, response=response: response)
                ) as client:
                    with self.assertRaises(AuditError):
                        _get_json(client, "/repos/a/b")

        def timeout(request):
            raise httpx.ReadTimeout("timed out")

        with httpx.Client(transport=httpx.MockTransport(timeout)) as client:
            with self.assertRaises(AuditError):
                _get_json(client, "/repos/a/b")

    @patch("auditor.services._get_json")
    def test_community_files_branch_encoding_and_cache(self, fetch):
        fetch.side_effect = [
            {"name": "b", "default_branch": "feature/a&other=bad", "private": False},
            [{"name": "tests", "type": "dir"}, {"name": "README-fake", "type": "file"}],
            [
                {"name": "SECURITY.md", "type": "file"},
                {"name": "PULL_REQUEST_TEMPLATE.md", "type": "file"},
            ],
            [{"name": "README.md", "type": "file"}],
            [{"name": "notes.txt", "type": "file"}],
            [{"name": "config.yml", "type": "file"}],
            [],
            {"names": []},
        ]
        report = audit_repository("a", "b")
        checks = {item["key"]: item["passed"] for item in report["checks"]}
        for key in ["readme", "security", "pr-template", "tests"]:
            self.assertTrue(checks[key])
        self.assertFalse(checks["ci"])
        self.assertFalse(checks["issue-template"])
        self.assertIn("ref=feature%2Fa%26other%3Dbad", fetch.call_args_list[1].args[1])
        self.assertEqual(audit_repository("A", "B"), report)
        self.assertEqual(fetch.call_count, 8)

    @patch("auditor.services._get_json", return_value={"private": True})
    def test_private_repository_not_cached(self, fetch):
        with self.assertRaises(AuditError):
            audit_repository("a", "private")
        self.assertIsNone(cache.get("audit:v2:a/private"))

    @patch("auditor.views.audit_repository", return_value={"score": 80})
    def test_json_download(self, audit):
        response = self.client.get("/report.json", {"repo": "a/b"})
        self.assertEqual(response.json(), {"score": 80})
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertEqual(self.client.get("/report.json").status_code, 400)
