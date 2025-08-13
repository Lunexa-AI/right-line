# Configuration Files

This directory contains all configuration files that were previously scattered in the root directory.

## ⚙️ Files

### Development Tools
- **.cursorrules** - AI coding assistant rules and guidelines
- **.pre-commit-config.yaml** - Git pre-commit hooks configuration
- **.pydocstyle** - Python docstring style configuration
- **.markdownlint.json** - Markdown linting rules
- **.secrets.baseline** - Secrets detection baseline

### Docker
- **.dockerignore** - Files to exclude from Docker builds

### Environment Configuration
- **development.env** - Development environment variables
- **production.env** - Production environment template

## 🔗 Symlinks

Some files have symlinks in the root directory for tool compatibility:
- Root `.pre-commit-config.yaml` → `config/.pre-commit-config.yaml`

## 📚 Related Documentation

- **Configuration Guide**: [../docs/configuration.md](../docs/configuration.md)
- **CI Management**: [../docs/development/ci-management.md](../docs/development/ci-management.md)
- **Contributing Guide**: [../docs/project/CONTRIBUTING.md](../docs/project/CONTRIBUTING.md)

---

*This organization keeps configuration files organized while maintaining tool compatibility.*
