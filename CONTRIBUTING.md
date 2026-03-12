# Contributing to Noesium

Thank you for your interest in contributing to Noesium! This guide will help you get started with development.

## Development Setup

### Prerequisites

- **Python >= 3.11** - The project uses modern Python features
- **uv** - Fast Python package manager (recommended)
- **Git** - Version control

### Install uv

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### Clone and Setup

```bash
# Clone the repository
git clone https://github.com/mirasoth/noesium.git
cd noesium

# Install all workspace packages
uv sync --all-packages --extra dev --extra all

# Setup pre-commit hooks (optional but recommended)
uv run pre-commit install
```

## Project Structure

The repository is organized as a monorepo with three subprojects:

```
noesium/
├── noesium/              # Core framework package
│   ├── src/noesium/      # Framework source code
│   ├── tests/            # Test suite
│   └── pyproject.toml    # Package configuration
├── noeagent/             # CLI/TUI application
│   ├── src/noeagent/     # Application source
│   ├── tests/            # Test suite
│   └── pyproject.toml
├── docs/                 # Documentation
├── examples/             # Example code
└── pyproject.toml        # Workspace configuration
```

### Subprojects

1. **noesium** - Core cognitive agentic framework
   - Memory management
   - Tool execution system
   - Subagent orchestration
   - LLM integration

2. **noeagent** - Multi-agent CLI/TUI application
   - Interactive terminal UI
   - Task planning
   - Ask/Agent dual modes

## Development Workflow

### Running Tests

```bash
# Run all tests
make test-all

# Run tests for specific package
make test-noesium
make test-noeagent

# Run unit tests only
make test-unit

# Run integration tests
make test-integration

# Run tests with coverage
make test-coverage
```

### Code Quality

```bash
# Format code
make format

# Check formatting
make format-check

# Run linters
make lint

# Auto-fix linting issues
make autofix

# Run all quality checks
make quality
```

### Building Packages

```bash
# Build all packages
make build-all

# Build specific package
make build-noesium
make build-noeagent
```

### Running Applications

```bash
# Run noeagent TUI
cd noeagent
uv run noeagent
```

## Making Changes

### 1. Create a Branch

```bash
git checkout -b feature/your-feature-name
```

Use descriptive branch names:
- `feature/add-new-toolkit` - New features
- `fix/memory-leak` - Bug fixes
- `docs/api-reference` - Documentation
- `refactor/agent-core` - Code refactoring

### 2. Make Your Changes

- Follow the existing code style
- Write meaningful commit messages
- Add tests for new functionality
- Update documentation as needed

### 3. Code Style Guidelines

**Python:**
- Use **Black** for formatting (line-length: 120)
- Use **isort** for import sorting
- Follow **PEP 8** conventions
- Add type hints where appropriate
- Write docstrings for public APIs

**TypeScript/React:**
- Use **Prettier** for formatting
- Follow existing component patterns
- Use TypeScript strict mode
- Add types for all props

### 4. Run Quality Checks

```bash
# Format code
make format

# Run linters
make lint

# Run tests
make test-all

# Run type checking
uv run mypy noesium/src noeagent/src
```

### 5. Commit Changes

Write clear, descriptive commit messages:

```
feat: add support for Ollama local models

- Add OllamaLLM provider class
- Implement streaming support
- Add configuration options
- Update documentation

Closes #123
```

Follow conventional commits:
- `feat:` - New features
- `fix:` - Bug fixes
- `docs:` - Documentation changes
- `test:` - Test additions/changes
- `refactor:` - Code refactoring
- `chore:` - Maintenance tasks

### 6. Push and Create PR

```bash
git push origin feature/your-feature-name
```

Create a Pull Request on GitHub with:
- Clear description of changes
- Reference to related issues
- Screenshots for UI changes
- Test results

## Testing

### Unit Tests

Write unit tests for:
- New functions and methods
- Edge cases and error handling
- Utility functions

```python
def test_memory_store():
    """Test memory store functionality."""
    store = MemoryStore()
    store.add("key", "value")
    assert store.get("key") == "value"
```

### Integration Tests

Write integration tests for:
- API endpoints
- Database interactions
- External service integrations

Mark integration tests with:

```python
import pytest

@pytest.mark.integration
def test_llm_provider():
    """Test LLM provider integration."""
    ...
```

### Running Specific Tests

```bash
# Run specific test file
uv run pytest tests/unit/test_memory.py

# Run specific test
uv run pytest tests/unit/test_memory.py::test_memory_store

# Run tests matching pattern
uv run pytest -k "memory" tests/

# Run with verbose output
uv run pytest -v tests/
```

## Documentation

### Code Documentation

- Add docstrings to all public functions, classes, and modules
- Use Google-style docstrings:

```python
def process_task(task: Task) -> Result:
    """Process a task and return the result.

    Args:
        task: The task to process.

    Returns:
        The processing result.

    Raises:
        ValueError: If task is invalid.

    Example:
        >>> task = Task(description="Example")
        >>> result = process_task(task)
    """
    ...
```

### User Documentation

- Update relevant guides in `docs/`
- Add examples to `examples/`
- Update README files as needed

### RFC Specifications

For architectural changes:
1. Create RFC in `docs/specs/` following RFC-0001
2. Get approval before implementation
3. Create implementation guide in `docs/impl/`

## Release Process

### Version Management

Versions are managed independently for each package:

- **noesium**: Core framework version
- **noeagent**: Application version

### Creating a Release

1. **Update version** in package's `pyproject.toml`
2. **Update CHANGELOG.md** with changes
3. **Run full test suite**: `make ci`
4. **Build package**: `make build`
5. **Create git tag**: `git tag noesium-v0.4.0`
6. **Push tag**: `git push origin noesium-v0.4.0`
7. **Create GitHub release** with changelog
8. **Publish to PyPI**: `make publish`

### PyPI Publishing

```bash
# Set PyPI token
export UV_PUBLISH_TOKEN=pypi-...

# Publish to PyPI
make publish

# Or publish to TestPyPI first
make publish-test
```

## Project Governance

### Code Review

All changes require:
- At least one approving review
- Passing CI checks
- No merge conflicts

### Issue Tracking

Use GitHub Issues for:
- Bug reports
- Feature requests
- Questions and discussions

### RFC Process

For significant changes:
1. Create RFC in `docs/specs/`
2. Discuss with maintainers
3. Get approval
4. Implement with guide in `docs/impl/`

## Getting Help

- **Documentation**: See `docs/` directory
- **Issues**: GitHub Issues for bugs and features
- **Discussions**: GitHub Discussions for questions

## Code of Conduct

- Be respectful and inclusive
- Welcome newcomers
- Focus on constructive feedback
- Follow GitHub's community guidelines

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to Noesium! 🚀