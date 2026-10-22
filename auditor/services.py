# FILE: auditor/services.py
"""Read-only GitHub API client and repository health scoring."""

import json
import os
import re
from urllib.parse import urlencode, urlparse

import httpx
from django.core.cache import cache
from django.utils import timezone

GITHUB_API = "https://api.github.com"
TIMEOUT_SECONDS = 8.0
MAX_RESPONSE_BYTES = 1_000_000


class AuditError(Exception):
    """Expected error while fetching or validating repository data."""


def parse_repo_input(value: str) -> tuple[str, str]:
    """Accept owner/repo or a public github.com URL and return normalized parts."""
    value = value.strip()
    if not value or len(value) > 300:
        raise AuditError("Enter a repository URL or owner/repository (maximum 300 characters).")
    try:
        if value.startswith(("github.com/", "www.github.com/")) or "://" in value:
            parsed = urlparse(value if "://" in value else f"https://{value}")
            if (
                parsed.scheme not in {"https", "http"}
                or parsed.hostname not in {"github.com", "www.github.com"}
                or parsed.username
                or parsed.password
                or parsed.port
            ):
                raise AuditError("Please enter a public github.com repository URL.")
            parts = parsed.path.strip("/").split("/")
        else:
            parts = value.strip("/").split("/")
            if len(parts) != 2:
                raise AuditError("Use the format owner/repository.")
    except ValueError as exc:
        raise AuditError("That repository URL is not valid.") from exc
    if len(parts) < 2:
        raise AuditError("Use the format owner/repository.")
    owner, repo = parts[0], parts[1]
    repo = re.sub(r"\.git$", "", repo)
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", owner) or not re.fullmatch(
        r"[A-Za-z0-9_.-]{1,100}", repo
    ):
        raise AuditError("The repository owner or name contains unsupported characters.")
    if owner in {".", ".."} or repo in {".", ".."}:
        raise AuditError("That repository path is not valid.")
    return owner, repo


def _headers() -> dict[str, str]:
    """Build GitHub API headers, optionally using a server-side token."""
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "RepoRadar-PandaDev",
    }
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _get_json(client: httpx.Client, path: str, *, optional: bool = False):
    """Fetch a JSON endpoint and translate common GitHub failures to helpful errors."""
    try:
        with client.stream("GET", f"{GITHUB_API}{path}", headers=_headers()) as response:
            if response.status_code == 404 and optional:
                return []
            if response.status_code == 404:
                raise AuditError("Repository not found, or it is private.")
            if response.status_code in {403, 429}:
                raise AuditError("GitHub refused or rate limited the request. Try again later.")
            if response.status_code != 200:
                raise AuditError(
                    f"GitHub API returned HTTP {response.status_code}. Try again later."
                )
            body = bytearray()
            for chunk in response.iter_bytes(chunk_size=65536):
                body.extend(chunk)
                if len(body) > MAX_RESPONSE_BYTES:
                    raise AuditError("GitHub returned an unexpectedly large response.")
            data = json.loads(body)
            expected = list if "/contents" in path or "/releases?" in path else dict
            if not isinstance(data, expected):
                raise AuditError("GitHub returned an unexpected response format.")
            if isinstance(data, list) and any(
                not isinstance(item, dict) or not isinstance(item.get("name", ""), str)
                for item in data
            ):
                raise AuditError("GitHub returned invalid directory or release data.")
            if isinstance(data, dict):
                names = data.get("names", [])
                if not isinstance(names, list) or any(not isinstance(n, str) for n in names):
                    raise AuditError("GitHub returned invalid topic data.")
            return data
    except (httpx.HTTPError, ValueError) as exc:
        raise AuditError(
            "GitHub could not be reached or returned invalid data. Try again later."
        ) from exc


def audit_repository(owner: str, repo: str) -> dict:
    """Collect repository metadata and score community-readiness signals."""
    owner, repo = parse_repo_input(f"{owner}/{repo}")
    cache_key = f"audit:v2:{owner.lower()}/{repo.lower()}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    with httpx.Client(timeout=TIMEOUT_SECONDS, follow_redirects=False) as client:
        repository = _get_json(client, f"/repos/{owner}/{repo}")
        if repository.get("private"):
            raise AuditError("Private repositories are not supported.")
        default_branch = repository.get("default_branch") or "main"
        branch_query = urlencode({"ref": default_branch})
        contents = _get_json(client, f"/repos/{owner}/{repo}/contents?{branch_query}")
        root_names = {
            item.get("name", "").lower()
            for item in contents
            if isinstance(item, dict) and item.get("type") == "file"
        }
        github_files = _get_json(
            client, f"/repos/{owner}/{repo}/contents/.github?{branch_query}", optional=True
        )
        docs_files = _get_json(
            client, f"/repos/{owner}/{repo}/contents/docs?{branch_query}", optional=True
        )
        community_names = root_names | {
            item.get("name", "").lower()
            for item in github_files + docs_files
            if isinstance(item, dict) and item.get("type") == "file"
        }
        workflows = _get_json(
            client,
            f"/repos/{owner}/{repo}/contents/.github/workflows?{branch_query}",
            optional=True,
        )
        workflow_names = (
            {
                item.get("name", "").lower()
                for item in workflows
                if isinstance(item, dict)
                and item.get("type") == "file"
                and item.get("name", "").endswith((".yml", ".yaml"))
            }
            if isinstance(workflows, list)
            else set()
        )
        issue_templates = _get_json(
            client,
            f"/repos/{owner}/{repo}/contents/.github/ISSUE_TEMPLATE?{branch_query}",
            optional=True,
        )
        issue_template_names = (
            {
                item.get("name", "").lower()
                for item in issue_templates
                if isinstance(item, dict)
                and item.get("type") == "file"
                and item.get("name", "").lower() != "config.yml"
                and item.get("name", "").endswith((".md", ".yml", ".yaml"))
            }
            if isinstance(issue_templates, list)
            else set()
        )
        releases = _get_json(client, f"/repos/{owner}/{repo}/releases?per_page=1")
        topics_data = _get_json(client, f"/repos/{owner}/{repo}/topics")
        topics = topics_data.get("names", []) if isinstance(topics_data, dict) else []

    checks = []

    def add(key, label, passed, points, maximum, detail, recommendation):
        checks.append(
            {
                "key": key,
                "label": label,
                "passed": bool(passed),
                "points": points if passed else 0,
                "maximum": maximum,
                "detail": detail,
                "recommendation": "" if passed else recommendation,
            }
        )

    has_readme = any((name == "readme" or name.startswith("readme.")) for name in community_names)
    has_license = (
        "license" in root_names or "license.md" in root_names or "license.txt" in root_names
    )
    has_contributing = any(
        (name == "contributing" or name.startswith("contributing.")) for name in community_names
    )
    has_code_of_conduct = any(
        (name == "code_of_conduct" or name.startswith("code_of_conduct."))
        for name in community_names
    )
    has_security = any(
        (name == "security" or name.startswith("security.")) for name in community_names
    )
    has_changelog = any(name.startswith("changelog") or name == "history.md" for name in root_names)
    has_ci = bool(workflow_names)
    has_issue_template = bool(issue_template_names) or any(
        name.startswith("issue_template") for name in root_names
    )
    has_pr_template = "pull_request_template.md" in community_names
    has_description = bool(repository.get("description"))
    has_topics = bool(topics)
    has_release = bool(releases)
    has_homepage = bool(repository.get("homepage"))
    all_root_names = {item.get("name", "").lower() for item in contents if isinstance(item, dict)}
    has_tests_signal = any(
        name in all_root_names for name in ("tests", "test", "pytest.ini", "tox.ini")
    )

    add(
        "readme",
        "README",
        has_readme,
        15,
        15,
        "Explains what the project does and how to use it."
        if has_readme
        else "No root README was found.",
        "Add a README with purpose, screenshots, installation, usage, and examples.",
    )
    add(
        "license",
        "Open-source license",
        has_license,
        12,
        12,
        "A root license file was found." if has_license else "No root license file was found.",
        "Add a recognized open-source license so users understand how they may use the project.",
    )
    add(
        "description",
        "Repository description",
        has_description,
        8,
        8,
        repository.get("description") or "No description set.",
        "Write a concise description in GitHub repository settings.",
    )
    add(
        "contributing",
        "Contribution guide",
        has_contributing,
        8,
        8,
        "Contribution guidance was found." if has_contributing else "No contribution guide found.",
        "Add CONTRIBUTING.md with setup, testing, and pull request expectations.",
    )
    add(
        "code-of-conduct",
        "Code of conduct",
        has_code_of_conduct,
        5,
        5,
        "Community conduct guidance was found."
        if has_code_of_conduct
        else "No code of conduct found.",
        "Add a CODE_OF_CONDUCT.md to establish community expectations.",
    )
    add(
        "ci",
        "CI workflow",
        has_ci,
        12,
        12,
        f"Found {len(workflow_names)} workflow file(s)."
        if has_ci
        else "No GitHub Actions workflow found.",
        "Add a GitHub Actions workflow that runs tests and lint checks on pull requests.",
    )
    add(
        "issue-template",
        "Issue templates",
        has_issue_template,
        6,
        6,
        "Issue template configuration was found."
        if has_issue_template
        else "No issue templates found.",
        "Add bug report and feature request templates under .github/ISSUE_TEMPLATE/.",
    )
    add(
        "pr-template",
        "Pull request template",
        has_pr_template,
        5,
        5,
        "A pull request template was found."
        if has_pr_template
        else "No pull request template found.",
        "Add .github/PULL_REQUEST_TEMPLATE.md with a checklist and testing notes.",
    )
    add(
        "security",
        "Security policy",
        has_security,
        7,
        7,
        "A security policy was found." if has_security else "No security policy found.",
        "Add SECURITY.md explaining how to report vulnerabilities responsibly.",
    )
    add(
        "changelog",
        "Changelog",
        has_changelog,
        5,
        5,
        "A changelog was found." if has_changelog else "No changelog found.",
        "Add CHANGELOG.md to document user-visible changes.",
    )
    add(
        "tests",
        "Test structure",
        has_tests_signal,
        7,
        7,
        "A likely test directory or test config was found."
        if has_tests_signal
        else "No obvious test directory/config found.",
        "Add automated tests and document how to run them.",
    )
    add(
        "release",
        "Published release",
        has_release,
        5,
        5,
        "At least one GitHub release was found."
        if has_release
        else "No published GitHub release found.",
        "Publish a tagged release once the project is usable and versioned.",
    )
    add(
        "topics",
        "Repository topics",
        has_topics,
        3,
        3,
        f"Found topics: {', '.join(topics[:6])}." if has_topics else "No repository topics set.",
        "Add a few accurate GitHub topics so developers can discover the project.",
    )
    add(
        "homepage",
        "Project homepage",
        has_homepage,
        2,
        2,
        repository.get("homepage") or "No homepage URL set.",
        "Add a docs site, live demo, or project website if available.",
    )

    maximum = sum(check["maximum"] for check in checks)
    earned = sum(check["points"] for check in checks)
    score = round(earned / maximum * 100) if maximum else 0
    if score >= 85:
        grade, grade_label = "A", "Contributor-ready"
    elif score >= 70:
        grade, grade_label = "B", "Promising project"
    elif score >= 50:
        grade, grade_label = "C", "Needs a few essentials"
    elif score >= 30:
        grade, grade_label = "D", "Early-stage setup"
    else:
        grade, grade_label = "E", "Just getting started"

    recommendations = [check for check in checks if not check["passed"]]
    recommendations.sort(key=lambda item: item["maximum"], reverse=True)
    report = {
        "audited_at": timezone.now().isoformat(),
        "archived": bool(repository.get("archived")),
        "owner": owner,
        "name": repository.get("name", repo),
        "full_name": repository.get("full_name", f"{owner}/{repo}"),
        "url": f"https://github.com/{owner}/{repo}",
        "description": repository.get("description")
        or "No repository description has been added yet.",
        "language": repository.get("language") or "Not specified",
        "stars": repository.get("stargazers_count", 0),
        "forks": repository.get("forks_count", 0),
        "open_issues": repository.get("open_issues_count", 0),
        "default_branch": default_branch,
        "updated_at": repository.get("updated_at", ""),
        "created_at": repository.get("created_at", ""),
        "topics": topics,
        "homepage": repository.get("homepage") or "",
        "score": score,
        "grade": grade,
        "grade_label": grade_label,
        "checks": checks,
        "recommendations": recommendations,
        "passed_count": sum(1 for check in checks if check["passed"]),
        "total_count": len(checks),
    }
    cache.set(cache_key, report, timeout=300)
    return report


# END OF FILE
# SIGNED: admin@thepandadev.com
