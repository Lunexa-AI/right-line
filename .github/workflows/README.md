# CI/CD Workflows for RightLine

## 🚨 Currently Disabled for Solo Development

All CI/CD workflows are currently **disabled** to allow for rapid MVP development without CI friction.

## 📋 Available Workflows

### 1. **ci.yml.disabled** - Main CI Pipeline
- Runs linting (ruff, black, mypy)
- Runs security scans (bandit, safety)
- Runs unit and integration tests
- Checks code coverage
- Matrix testing on Python 3.11 and 3.12
- Build verification

**To enable:** 
```bash
mv .github/workflows/ci.yml.disabled .github/workflows/ci.yml
```

### 2. **security.yml.disabled** - Security Scanning
- Dependency vulnerability scanning
- Container security with Trivy
- SAST with Semgrep and CodeQL
- Secret detection with Gitleaks
- License compliance checking

**To enable:**
```bash
mv .github/workflows/security.yml.disabled .github/workflows/security.yml
```

### 3. **release.yml.disabled** - Release & Deployment
- Automated versioning
- Docker image building and pushing
- Multi-environment deployment
- Blue-green deployment for production
- Automatic changelog generation

**To enable:**
```bash
mv .github/workflows/release.yml.disabled .github/workflows/release.yml
```

### 4. **dependabot.yml.disabled** - Dependency Updates
Located in `.github/dependabot.yml.disabled`
- Automated dependency updates
- Security patches
- Grouped updates to reduce noise

**To enable:**
```bash
mv .github/dependabot.yml.disabled .github/dependabot.yml
```

## 🚀 Enabling CI/CD

When you're ready to enable CI/CD (e.g., when the team grows):

1. **Enable workflows one by one:**
   ```bash
   # Start with the main CI
   mv .github/workflows/ci.yml.disabled .github/workflows/ci.yml
   
   # Then add security scanning
   mv .github/workflows/security.yml.disabled .github/workflows/security.yml
   
   # Enable dependency updates
   mv .github/dependabot.yml.disabled .github/dependabot.yml
   ```

2. **Configure secrets in GitHub:**
   - `CODECOV_TOKEN` - For code coverage reporting
   - `SAFETY_API_KEY` - For vulnerability scanning (optional)
   - `SLACK_WEBHOOK_URL` - For notifications (optional)
   - `STAGING_KUBECONFIG` - For staging deployment
   - `PRODUCTION_KUBECONFIG` - For production deployment

3. **Set up branch protection rules:**
   - Require PR reviews
   - Require status checks to pass
   - Require branches to be up to date
   - Include administrators

4. **Configure environments:**
   - Create `staging` and `production` environments
   - Add required reviewers for production
   - Set environment secrets

## 📊 CI Performance

The workflows are optimized for speed:
- **CI Pipeline:** ~5 minutes
- **Security Scan:** ~10 minutes  
- **Release:** ~15 minutes

All workflows use:
- Dependency caching
- Parallel jobs
- Matrix strategies
- Fail-fast configurations

## 🔧 Customization

### Adjusting for Your Needs

1. **Reduce test coverage threshold:**
   Edit `ci.yml` and change `--cov-fail-under=80` to your desired threshold

2. **Skip certain security checks:**
   Comment out jobs in `security.yml` you don't need

3. **Change deployment targets:**
   Update the deployment sections in `release.yml`

4. **Modify Python versions:**
   Edit the matrix in `ci.yml` to test different Python versions

## 🎯 Solo Developer Workflow

While CI is disabled, use these local commands:

```bash
# Run all checks locally
make lint          # Linting
make format        # Auto-format
make test          # Run tests
make security      # Security scan

# Or all at once
make lint format test security
```

The pre-commit hooks will catch most issues before commit:
```bash
pre-commit run --all-files
```

## 📈 Gradual Adoption

Suggested order for enabling CI:

1. **Phase 1:** Enable `ci.yml` with only linting
2. **Phase 2:** Add tests to `ci.yml`
3. **Phase 3:** Enable `dependabot.yml` for security updates
4. **Phase 4:** Enable `security.yml` for comprehensive scanning
5. **Phase 5:** Enable `release.yml` for automated deployments

## ❓ Questions?

- Check the individual workflow files for detailed comments
- See [GitHub Actions documentation](https://docs.github.com/en/actions)
- Review the [ARCHITECTURE.md](../../ARCHITECTURE.md) for deployment strategies
