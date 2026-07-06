# Contributing to AI Security Agent

Thank you for your interest in contributing. This document provides guidelines for contributing to the project.

## Project Structure

```
ai-security-agent/
├── src/
│   └── security_agent/       # AI Security Agent source code
├── management_server/
│   └── src/
│       ├── management_server/ # Management Server source code
│       └── discord_bot/       # Discord Relay Bot source code
├── config/                    # Agent configuration
├── rules/                     # Detection rules (YAML)
├── correlation/               # Attack chain definitions
├── database/                  # Database migrations
├── tests/                     # Agent test suite
├── tools/                     # Development and testing tools
│   └── integration_harness/   # Integration testing framework
├── docs/                      # Documentation
└── scripts/                   # Utility scripts
```

## Coding Style

- **Python**: Follow [PEP 8](https://peps.python.org/pep-0008/) with line length limited to 120 characters
- **Type hints**: Required for all function signatures and public APIs
- **Docstrings**: Use Google-style docstrings for public modules, classes, and functions
- **Imports**: Group standard library, third-party, and local imports; sort alphabetically

The project uses [Ruff](https://docs.astral.sh/ruff/) for linting and formatting. Configuration is in `pyproject.toml`.

## Branch Naming

- `main` — stable release branch
- `feature/<description>` — new features
- `fix/<description>` — bug fixes
- `docs/<description>` — documentation changes
- `refactor/<description>` — code refactoring

Use kebab-case for branch names. Keep descriptions concise.

## Pull Request Process

1. Create a feature or fix branch from `main`
2. Make your changes following the coding style
3. Add or update tests as needed
4. Run linting and tests locally
5. Submit a pull request to `main`
6. Ensure all CI checks pass
7. Request review from maintainers

## Issue Reporting

When reporting issues, include:

- A clear, descriptive title
- Steps to reproduce the issue
- Expected behavior and actual behavior
- Environment details (OS, Python version, package versions)
- Log output or error messages

Use the GitHub issue tracker: <https://github.com/joelslamospersson/ai-security-agent-rc1/issues>

## Testing

```bash
# Run all agent tests
pytest tests/

# Run all management server tests
cd management_server && pytest tests/

# Run with coverage
pytest --cov=security_agent --cov-report=term tests/
pytest --cov=management_server --cov-report=term tests/
```

Write tests for:

- New functionality
- Bug fixes
- Edge cases and boundary conditions
- Error handling paths

Tests use `pytest` with `pytest-asyncio` for async test support.

## Linting

```bash
# Check for linting issues
ruff check src/ tests/

# Automatically fix linting issues
ruff check --fix src/ tests/
```

The project enforces the following Ruff rule sets: E, F, I, N, W, UP, B, SIM, ARG, C4, RUF.

## Formatting

```bash
# Format code
ruff format src/ tests/
```

The project uses:
- Double quotes for strings
- Spaces for indentation (4 spaces)
- LF line endings

## Commit Message Guidelines

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

Types:
- `feat` — new feature
- `fix` — bug fix
- `docs` — documentation changes
- `refactor` — code refactoring
- `test` — adding or updating tests
- `chore` — maintenance tasks
- `style` — formatting changes
- `perf` — performance improvement

Example:
```
feat(detectors): add SSH impossible travel detection

Implements geolocation-based impossible travel detection for SSH
logins. Uses configurable distance and time thresholds.
```

## Code Review Expectations

- All code changes require review before merging
- Reviewers should focus on correctness, security, and maintainability
- Address all review comments before merging
- Keep pull requests focused on a single concern
- Large changes should be broken into smaller, reviewable PRs
