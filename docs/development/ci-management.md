# CI/CD Management Guide

## Overview

RightLine has comprehensive CI/CD and pre-commit hooks that can be enabled/disabled based on development phase and team size.

## Current Status

**Pre-commit hooks**: ❌ **DISABLED** (for solo MVP development)  
**GitHub Actions CI**: ❌ **DISABLED** (workflows exist but are `.disabled`)

## Pre-commit Hooks Management

### Disable Pre-commit Hooks (Current State)

For rapid MVP development without friction:

```bash
# Disable all git hooks
git config --local core.hooksPath /dev/null

# Verify hooks are disabled
git config --local core.hooksPath
# Should output: /dev/null
```

### Enable Pre-commit Hooks

When ready for team development or quality enforcement:

```bash
# Re-enable git hooks
git config --local --unset core.hooksPath

# Reinstall pre-commit hooks
poetry run pre-commit install

# Test hooks work
poetry run pre-commit run --all-files
```

### What Pre-commit Hooks Do

When enabled, they run on every commit:

- **Code formatting**: Black, Ruff, isort
- **Type checking**: mypy
- **Security scanning**: Bandit, detect-secrets
- **Documentation**: pydocstyle, markdownlint
- **Docker**: hadolint (Dockerfile linting)
- **Shell scripts**: shellcheck

## GitHub Actions CI Management

### Current State (Disabled)

All CI workflows are disabled with `.disabled` extension:
- `.github/workflows/ci.yml.disabled`
- `.github/workflows/security.yml.disabled`
- `.github/workflows/deploy-staging.yml.disabled`
- `.github/workflows/deploy-production.yml.disabled`

### Enable GitHub Actions CI

When ready for automated CI (team growth, approaching production):

```bash
# Enable main CI workflow
mv .github/workflows/ci.yml.disabled .github/workflows/ci.yml

# Enable security scanning
mv .github/workflows/security.yml.disabled .github/workflows/security.yml

# Enable dependency updates
mv .github/dependabot.yml.disabled .github/dependabot.yml

# Enable deployment workflows (optional)
mv .github/workflows/deploy-staging.yml.disabled .github/workflows/deploy-staging.yml
mv .github/workflows/deploy-production.yml.disabled .github/workflows/deploy-production.yml
```

### Configure CI Secrets

Before enabling CI, set up required secrets in GitHub:

```bash
# Repository secrets (Settings > Secrets and variables > Actions)
CODECOV_TOKEN              # Code coverage reporting
SENTRY_AUTH_TOKEN          # Error tracking
SLACK_WEBHOOK_URL          # Notifications (optional)

# Environment secrets (for deployment workflows)
STAGING_DATABASE_URL       # Staging database
PRODUCTION_DATABASE_URL    # Production database
# ... see .github/environments/README.md for full list
```

## Development Workflow Recommendations

### Phase 1: Solo MVP Development (Current)
- ✅ Pre-commit hooks: **DISABLED**
- ✅ GitHub Actions: **DISABLED**
- ✅ Manual quality checks: `make lint`, `make test`

### Phase 2: Team Development
- ✅ Pre-commit hooks: **ENABLED**
- ❌ GitHub Actions: **DISABLED** (optional)
- ✅ Manual PR reviews

### Phase 3: Production Readiness
- ✅ Pre-commit hooks: **ENABLED**
- ✅ GitHub Actions: **ENABLED**
- ✅ Automated deployments
- ✅ Security scanning

## Manual Quality Checks (Always Available)

Even with CI disabled, you can run quality checks manually:

```bash
# Code quality
make lint          # Run linters
make format        # Auto-format code
make test          # Run tests
make security      # Security checks

# Or run all checks
make check         # Runs lint, test, security
```

## Quick Reference Commands

```bash
# DISABLE pre-commit hooks (current state)
git config --local core.hooksPath /dev/null

# ENABLE pre-commit hooks
git config --local --unset core.hooksPath
poetry run pre-commit install

# ENABLE GitHub Actions CI
mv .github/workflows/ci.yml.disabled .github/workflows/ci.yml

# DISABLE GitHub Actions CI
mv .github/workflows/ci.yml .github/workflows/ci.yml.disabled

# Check current hook status
git config --local core.hooksPath

# Run quality checks manually
make lint test security
```

## Troubleshooting

### Pre-commit Hooks Taking Too Long

```bash
# Skip hooks for urgent commits
git commit --no-verify -m "urgent fix"

# Or disable temporarily
git config --local core.hooksPath /dev/null
```

### CI Failing on Enabled Workflows

```bash
# Check workflow status
gh run list

# View specific run
gh run view <run-id>

# Re-run failed jobs
gh run rerun <run-id>
```

### Dependency Conflicts

```bash
# Update pre-commit hooks
poetry run pre-commit autoupdate

# Clear pre-commit cache
poetry run pre-commit clean
```

## Best Practices

1. **Start simple**: Disable CI during rapid prototyping
2. **Enable gradually**: Add quality checks as codebase stabilizes
3. **Team coordination**: Enable pre-commit when multiple developers join
4. **Production readiness**: Enable full CI/CD before production deployment
5. **Documentation**: Keep this guide updated as workflows evolve

## Related Documentation

- [Contributing Guide](../CONTRIBUTING.md) - Development workflow
- [GitHub Environments](../.github/environments/README.md) - CI/CD secrets setup
- [Deployment Guide](../docs/deployment/README.md) - Production deployment
