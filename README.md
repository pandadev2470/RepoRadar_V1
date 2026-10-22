<!-- FILE: README.md -->
# RepoRadar 🚦

**A free, open-source GitHub repository health checker built with Django.**

RepoRadar audits a public GitHub repository and turns scattered project metadata into a practical launch-readiness report. It checks documentation, licensing, contribution guidance, issue templates, CI workflows, releases, topics, and other signals that help contributors understand and trust a project.

> RepoRadar is an advisory checklist, not a security scanner or a guarantee of project quality. It uses the public GitHub REST API and does not clone repositories or execute their code.

## Features

- **Instant repository audit** by `owner/repo` or a public GitHub URL.
- **Actionable score** with category-level results and prioritized next steps.
- **Contributor-readiness checks** for README, license, contributing guide, code of conduct, issue templates, pull request template, and CI.
- **Project maturity signals** for releases, descriptions, topics, stars, and recent activity.
- **GitHub API integration** using a token only when configured; works without one within GitHub's lower anonymous rate limit.
- **Responsive dark dashboard** with no frontend build step.
- **Django admin and ORM** for a familiar, extensible Python architecture.
- **Deployable** to Render with PostgreSQL or Docker; Vercel configuration is included for serverless experimentation.
- **Tests, lint configuration, environment example, and uv workflow.**

## Quick start

Requirements: Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
# 1. Install dependencies
uv sync --extra dev

# 2. Create your local environment file
# Windows PowerShell:
Copy-Item .env.example .env
# macOS/Linux:
# cp .env.example .env

# 3. Create database tables
uv run python manage.py migrate

# 4. Start the server
uv run python manage.py runserver
```

Open http://127.0.0.1:8000.

Optional: create a GitHub personal access token with public repository read access and set `GITHUB_TOKEN` in `.env`. No token is needed for a quick local demo, but anonymous API limits are lower. Keep tokens secret and never expose them in frontend code.

## Usage

Paste a repository URL such as `https://github.com/django/django` or `django/django` into the home page. RepoRadar fetches repository metadata and checks for common project health files and GitHub features. The report shows a score, check results, and recommended improvements.

## Configuration

| Variable | Purpose |
|---|---|
| `DJANGO_SECRET_KEY` | Secret key; set a strong value outside local development |
| `DJANGO_DEBUG` | `True` only for local development |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated allowed hostnames |
| `DATABASE_URL` | Database connection string; SQLite locally, PostgreSQL recommended in production |
| `GITHUB_TOKEN` | Optional token for higher GitHub API rate limits |
| `PORT` | Port used by the container/deployment platform |

## Deployment

### Render

This repository includes `render.yaml`. Push it to GitHub, create a new Blueprint in Render, and configure the generated `DJANGO_SECRET_KEY` plus optional `GITHUB_TOKEN` in the dashboard. The blueprint provisions PostgreSQL and runs migrations before starting Gunicorn.

### Docker

```bash
docker build -t reporadar .
docker run --rm -p 8000:8000 \
  -e DJANGO_SECRET_KEY='replace-with-a-long-secret' \
  -e DJANGO_DEBUG=False \
  -e DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1 \
  -e DJANGO_SECURE_SSL_REDIRECT=False \
  -e DATABASE_URL=sqlite:////app/data/db.sqlite3 \
  -v reporadar-data:/app/data \
  reporadar
```

### Vercel

A `vercel.json` and `api/index.py` adapter are included for serverless deployment experiments. Serverless filesystems are ephemeral, so use an external PostgreSQL database via `DATABASE_URL`. Configure `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=False`, `DJANGO_ALLOWED_HOSTS`, and `DATABASE_URL` in Vercel project settings. Verify current Vercel Python runtime compatibility before production deployment.

## Development

```bash
uv run python manage.py check
uv run python manage.py test
uv run ruff check .
```

## Project structure

```text
reporadar/
├── config/              # Django settings, URL configuration, WSGI and ASGI
├── auditor/             # Repository analysis service and views
├── auditor/templates/   # Dashboard and report templates
├── auditor/static/      # Minimal styling
├── api/                 # Vercel serverless adapter
├── Dockerfile
├── docker-compose.yml
├── render.yaml
├── vercel.json
├── pyproject.toml
└── requirements.txt
```

## Security and limitations

- Only public GitHub repositories are supported.
- RepoRadar makes read-only requests to the GitHub API and does not run repository code.
- Do not submit secrets or private repository URLs.
- The score is a transparent heuristic, not an official GitHub score.
- Production deployments should use HTTPS, a strong secret key, trusted hosts, dependency updates, and an external database.
- GitHub API rate limits apply. A configured token is recommended for shared deployments.
- Vercel is included as an optional deployment target, but its runtime and database integration should be validated against current platform limits before relying on it.

## Roadmap

- Compare two repository reports side by side
- Export reports as Markdown (JSON downloads are available)
- Add GitHub Actions badge and release freshness checks
- Add opt-in report history with user accounts
- Add maintainability checks for SECURITY.md and funding links
- Add localization and accessible report themes

## Contributing

Issues and pull requests are welcome. Please include tests for behavior changes and never commit secrets.

## License

MIT.

<!-- END OF FILE -->
<!-- SIGNED: admin@thepandadev.com -->

## Review updates and documentation

Reports now support JSON downloads, five-minute caching, archive warnings and improved
community-file detection. The responsive dashboard includes keyboard focus, skip
navigation and aligned desktop/mobile footers. Production requires a strong signing
key and explicitly configured proxy trust.

See [documentation](docs/README.md), [security review](docs/SECURITY_REVIEW.md),
[change log](docs/CHANGELOG.md), [folder tree](FOLDER_STRUCTURE.md) and
[contributor guidance](AGENTS.md). The security review records verification limits.
