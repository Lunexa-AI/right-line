# Contributing to RightLine

Thank you for your interest in contributing to RightLine! This document provides guidelines and instructions for contributing to the project.

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [How to Contribute](#how-to-contribute)
- [Development Workflow](#development-workflow)
- [Code Standards](#code-standards)
- [Testing](#testing)
- [Documentation](#documentation)
- [Pull Request Process](#pull-request-process)

## 📜 Code of Conduct

Please read and follow our [Code of Conduct](CODE_OF_CONDUCT.md). We are committed to providing a welcoming and inclusive environment for all contributors.

## 🚀 Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/right-line.git
   cd right-line
   ```
3. **Add upstream remote**:
   ```bash
   git remote add upstream https://github.com/Lunexa-AI/right-line.git
   ```

## 🛠️ Development Setup

### Prerequisites

- Python 3.11 or higher
- Poetry 1.7.1 or higher
- Docker and Docker Compose
- PostgreSQL 15+ with pgvector extension
- Redis 7+
- Git

### Initial Setup

```bash
# Install dependencies
make setup

# Copy and configure environment variables
cp .env.example .env
# Edit .env with your local configuration

# Run pre-commit hooks installation
pre-commit install

# Verify setup
make test
```

### Development Environment Options

#### Option 1: Docker Compose (Recommended)
```bash
# Start all services
make up

# View logs
make logs

# Stop services
make down
```

#### Option 2: Local Development
```bash
# Start databases (using Docker)
docker-compose up postgres redis meilisearch qdrant -d

# Run API in development mode
make dev
```

## 🤝 How to Contribute

### Types of Contributions

We welcome various types of contributions:

- **🐛 Bug Fixes**: Found a bug? Fix it!
- **✨ Features**: New features aligned with our roadmap
- **📚 Documentation**: Improvements to docs
- **🧪 Tests**: Additional test coverage
- **🎨 UI/UX**: Interface improvements
- **🌍 Translations**: Help with Shona/Ndebele translations
- **⚡ Performance**: Optimization and improvements

### Finding Issues to Work On

1. Check our [issue tracker](https://github.com/Lunexa-AI/right-line/issues)
2. Look for issues labeled:
   - `good first issue` - Great for newcomers
   - `help wanted` - We need help with these
   - `bug` - Known bugs to fix
   - `enhancement` - Feature improvements

3. Comment on the issue to claim it
4. If no issue exists, create one first to discuss

## 🔄 Development Workflow

### 1. Create a Feature Branch

```bash
# Update your local main branch
git checkout main
git pull upstream main

# Create a feature branch
git checkout -b feature/your-feature-name
# or
git checkout -b fix/issue-number-description
```

### 2. Make Your Changes

- Write clean, readable code
- Follow our code standards (see below)
- Add tests for new functionality
- Update documentation as needed

### 3. Commit Your Changes

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```bash
# Examples of good commit messages:
git commit -m "feat: add WhatsApp message parsing"
git commit -m "fix: correct rate limiting logic"
git commit -m "docs: update API documentation"
git commit -m "test: add retrieval service tests"
git commit -m "perf: optimize database queries"
```

Commit types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `perf`: Performance improvements
- `test`: Test additions or changes
- `chore`: Maintenance tasks

### 4. Run Tests and Checks

```bash
# Run all tests
make test

# Run linting
make lint

# Auto-format code
make format

# Run security checks
make security

# Or run everything
make check
```

### 5. Push Your Changes

```bash
git push origin feature/your-feature-name
```

## 📏 Code Standards

### Python Code Style

We use the following tools to maintain code quality:

- **Black**: Code formatting (line length 88)
- **Ruff**: Fast linting
- **mypy**: Static type checking
- **isort**: Import sorting

Configuration is in `pyproject.toml`.

### Key Guidelines

1. **Type Hints**: Always use type hints
   ```python
   def process_query(text: str, lang: str = "en") -> QueryResponse:
       ...
   ```

2. **Docstrings**: Use Google-style docstrings
   ```python
   def retrieve_sections(query: str, limit: int = 10) -> list[Section]:
       """Retrieve relevant law sections for a query.
       
       Args:
           query: The search query text
           limit: Maximum number of results
           
       Returns:
           List of matching Section objects
           
       Raises:
           RetrievalError: If search fails
       """
   ```

3. **Async First**: Prefer async/await for I/O operations
   ```python
   async def fetch_document(doc_id: str) -> Document:
       async with httpx.AsyncClient() as client:
           response = await client.get(f"/documents/{doc_id}")
           return Document(**response.json())
   ```

4. **Error Handling**: Use specific exceptions
   ```python
   class RetrievalError(Exception):
       """Raised when document retrieval fails."""
       pass
   ```

5. **Security**: Never hardcode secrets or credentials

### Project Structure

Follow our established structure:
```
services/     # Microservices (api, retrieval, etc.)
libs/         # Shared libraries
tests/        # Test files mirror source structure
docs/         # Documentation
scripts/      # Utility scripts
```

## 🧪 Testing

### Test Requirements

- Write tests for all new functionality
- Maintain or improve code coverage
- Tests should be fast and isolated

### Running Tests

```bash
# Run all tests
make test

# Run specific test file
pytest tests/unit/test_retrieval.py

# Run with coverage
make test-coverage

# Run specific test marker
pytest -m "not slow"
```

### Test Structure

```python
# tests/unit/services/retrieval/test_search.py
import pytest
from services.retrieval.search import hybrid_search

@pytest.mark.asyncio
async def test_hybrid_search_returns_results():
    """Test that hybrid search returns relevant results."""
    results = await hybrid_search("theft penalty")
    assert len(results) > 0
    assert results[0].confidence > 0.5
```

## 📚 Documentation

### Code Documentation

- All public functions must have docstrings
- Complex logic should have inline comments
- Update relevant .md files when adding features

### API Documentation

- API endpoints auto-documented via FastAPI
- Update OpenAPI schema descriptions
- Add request/response examples

## 🔀 Pull Request Process

### Before Submitting

1. **Update your branch**:
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

2. **Ensure all checks pass**:
   ```bash
   make check
   ```

3. **Update documentation** if needed

4. **Add tests** for new functionality

### Submitting a PR

1. Go to [GitHub](https://github.com/Lunexa-AI/right-line)
2. Click "New Pull Request"
3. Select your fork and branch
4. Fill out the PR template:
   - Clear title and description
   - Link related issues
   - List major changes
   - Include testing steps

### PR Title Format

Follow conventional commits format:
- `feat: add temporal query support`
- `fix: resolve memory leak in retrieval service`
- `docs: update deployment guide`

### Review Process

1. Automated checks will run
2. A maintainer will review your code
3. Address any feedback
4. Once approved, your PR will be merged

### After Merge

- Delete your feature branch
- Update your local main:
  ```bash
  git checkout main
  git pull upstream main
  ```

## 🎯 Development Tips

### Local Development

1. **Use the Makefile**: Common commands are available via `make`
2. **Check logs**: `make logs` to see service output
3. **Hot reload**: FastAPI auto-reloads on code changes
4. **Debug mode**: Set `LOG_LEVEL=DEBUG` in `.env`

### Performance Considerations

- Keep response times under 2 seconds
- Use caching where appropriate
- Optimize database queries
- Profile before optimizing

### Security Best Practices

- Never commit secrets
- Use environment variables
- Validate all inputs
- Follow OWASP guidelines
- Run security checks: `make security`

## 📊 Performance Standards

Your contribution should maintain our performance standards:

- API response time: P95 < 2s
- Test execution: < 30s for unit tests
- Memory usage: < 1GB per service
- Database queries: < 100ms

## 🆘 Getting Help

- **Discord**: [Join our Discord](https://discord.gg/rightline) (coming soon)
- **Discussions**: [GitHub Discussions](https://github.com/Lunexa-AI/right-line/discussions)
- **Issues**: [GitHub Issues](https://github.com/Lunexa-AI/right-line/issues)

## 🙏 Recognition

Contributors will be:
- Listed in our [CONTRIBUTORS.md](CONTRIBUTORS.md) file
- Mentioned in release notes
- Given credit in documentation

## 📄 License

By contributing, you agree that your contributions will be licensed under the same [MIT License](LICENSE) that covers the project.

---

Thank you for contributing to RightLine! Your efforts help make legal information more accessible in Zimbabwe. 🇿🇼
