# FrequencyMan Project Rules

## Project Overview
FrequencyMan is an Anki addon that allows it's user to sort new cards by word frequency, familiarity, and other useful factors.

## Codebase Overview

### Main Directories

- **`frequencyman/`** - Core addon code (card ranking, targets, language processing)
  - `frequencyman/lib/` - Utility modules (config, logging, caching, database)
  - `frequencyman/ui/` - Qt-based UI components (main window, tabs, dialogs)

- **`tests/`** - Test suite with `test_*.py` files matching source modules
  - `tools.py` - Shared test utilities and fixtures
  - `data/` - Test data files

- **`default_wf_lists/`** - Default word frequency lists for various languages
- **`user_files/`** - User-generated data and logs

### Key Files

- `__init__.py` - Main addon entry point (loaded by Anki)
- `config.json` - Default addon configuration
- `pyproject.toml` - Project dependencies and configuration
- `pytest.ini` - Pytest configuration

## Code Style & Standards

### File System Operations
- **ALWAYS use `pathlib.Path`** for all file system operations
- Never use `os.path` - prefer Path methods
- Type hints should use `Path` from `pathlib`
- Example: `def process_file(file_path: Path) -> None:`

### Type Hints
- All function signatures must have type hints
- Avoid `Any` unless absolutely necessary (it rarely is)
- Use modern syntax: `list[str]` not `List[str]`
- Use `from typing import` only for: `Callable`, `Optional`, `TypeVar`, etc.
- Use `from collections.abc import` for: `Generator`, `Iterator`, etc.
- Always include return type hints (use `-> None` when appropriate)

### Naming Conventions
- Use descriptive variable names
- Constants at class/module level: `UPPER_SNAKE_CASE`
- Private methods/attributes: `__double_leading_underscore`
- Boolean variables: prefer `is_`, `has_`, `should_` prefixes
- Use `is_too_large` not `is_large` for threshold checks

### Code Organization
- Extract magic numbers into named constants
- Keep methods focused (single responsibility)
- Extract complex logic into private helper methods
- Class constants should be defined right after class declaration

## Testing Requirements

### Test Coverage
- **All new code MUST have corresponding tests**
- Test files go in `tests/` directory
- Test filename format: `test_<module_name>.py`
- Use descriptive test function names: `test_<what>_<scenario>`

### Test Structure
- One test file per module being tested
- Use pytest fixtures when available
- Always include docstrings in new test files

## Root Directory Structure

### Main Code
- `frequencyman/` - Main addon code
- `frequencyman/lib/` - Utility libraries
- `frequencyman/ui/` - UI components

### Entry Point & Configuration
- `__init__.py` - Main addon entry point, loaded by Anki
- `config.json` - Default addon configuration
- `manifest.json` - Addon metadata for Anki
- `pytest.ini` - Pytest configuration
- `pyproject.toml` - Project configuration and dependencies

### Development & Build Files
- `create_release.py` - Script to create addon releases
- `create_default_wf_lists.py` - Generate default word frequency lists
- `test.py` - Development testing script
- `noxfile.py` - Nox automation configuration

### Data Directories
- `default_wf_lists/` - Default word frequency lists for various languages
- `user_files/` - User-generated data and logs
- `releases/` - Built release packages
- `typings/` - Type stubs for external libraries

### Tests
- `tests/` - All test files
- `tests/tools.py` - Shared test utilities
- `tests/data/` - Test data files

## Common Patterns

### Context Managers
- Use context managers for resource management
- Example: `with file_path.open('r', encoding='utf-8') as file:`
- Always specify encoding for text files

### Error Handling
- Use specific exceptions, not bare `except:`
- Provide helpful error messages

## Documentation

### Docstrings
- Keep simple methods self-documenting through clear names
- Format: `"""Brief description."""` for one-liners
- Skip docstrings for simple methods if other methods in the same (already existing) class are without docstrings
- Skip docstrings for function if other functions in the same (already existing) file are without docstrings

### Comments
- Explain WHY, not WHAT
- Keep comments up-to-date with code changes
- Prefer self-documenting code over comments

## Anki-Specific Guidelines

### Compatibility
- Ensure compatibility with Anki's Qt framework
- Use PyQt6 imports from `aqt.qt`
- Ensure compatibility with Python 3.9

#### PyQt6
- Ensure PyQt6 compatibility
- Qt6 requires enums to be prefixed with their type name. For example:
 `self.setWizardStyle(QWizard.ClassicStyle)` becomes `self.setWizardStyle(QWizard.WizardStyle.ClassicStyle)` and `f.setStyleHint(QFont.Monospace)` becomes `f.setStyleHint(QFont.StyleHint.Monospace)`.


## Workflow Summary

1. **Create code** following style guidelines
2. **Run linters** immediately: `ruff`, `mypy` and `pyright`
3. **Fix all issues** before proceeding
4. **Write tests** for the new code
5. **Run tests**: `pytest`
6. **Run linters again**: `ruff`, `mypy` and `pyright`
6. **Verify** all checks pass before considering task complete

## Quick Reference

### Create New Module
1. Create file in appropriate directory
2. Add proper imports and type hints
3. Write code following style guide
4. Run: `ruff check <file>', `mypy <file>` and `pyright <file>`
5. Create corresponding test file
6. Run: `pytest`

### Create New Test File
1. Create `tests/test_<module>.py`
2. Import what you're testing
3. Write comprehensive tests
4. Run: `pytest`
5. Check linters: `ruff check tests/test_<module>.py`

Remember: Clean code is better than clever code. Readability counts!
