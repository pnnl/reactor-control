# Coding Conventions - reactor-control

This document defines the coding standards, naming conventions, and formatting guidelines for the reactor-control project.

## Overview

- **Python Version:** >=3.14
- **Baseline Standard:** PEP 8
- **Goal:** Consistent, readable, and maintainable code across the project

## Naming Conventions

### Classes
Use PascalCase (CapWords) for class names.

### Functions and Methods
Use snake_case for function and method names.

### Variables
Use snake_case for variable names. Use descriptive names that indicate purpose.

### Constants
Use UPPER_SNAKE_CASE for module-level constants.

### Private Members
Use single underscore prefix for internal/private members.

### Module Exports
Use `__all__` lists to define public API surface for modules.

## Code Formatting

### Indentation
Use 4 spaces for indentation. No tabs.

### Line Length
Target maximum line length of 88 characters (Ruff default), with 79 characters as hard limit.

### String Formatting
Use f-strings for all string formatting operations.

### Multi-line Structures
Use trailing commas and place binary operators at the start of continuation lines.

### Whitespace
- Single space around operators
- No spaces inside parentheses/brackets
- Single blank line between logical sections
- Two blank lines between top-level functions/classes

## Type Hints

Type hints are required for all function signatures and class attributes.

### Optional Types
Use `Optional[T]` instead of `Union[T, None]`.

## Docstrings

All modules, classes, and public methods must have docstrings using Google-style format.

### Module Docstrings
Every `__init__.py` and module file should have a docstring.

### Class Docstrings
All classes must have docstrings describing their purpose and functionality.

### Method Docstrings
All public methods must have docstrings with Args and Returns sections.

## Import Organization

Imports should be organized in three groups with blank lines between:

1. Standard library imports
2. Third-party imports
3. Local application imports

Each group should be alphabetically ordered.

### Import Rules
- Each import on a separate line
- No `from module import *` statements
- Avoid relative imports deeper than one level when possible

## Error Handling

### Parameter Validation
Validate all parameters at the start of methods and return early with descriptive error messages.

### Return Values on Error
- Value-returning functions: Return `None` on error
- Boolean functions: Return `False` on error

### Exception Handling
Catch specific exceptions and provide meaningful error messages.

## Logging

### Module-Level Loggers
Create module-level loggers using `__name__`.

### Instance-Level Loggers
Create instance-level loggers that include class name for better filtering.

### Log Levels
Use appropriate log levels:
- `DEBUG`: Detailed diagnostic information
- `INFO`: General informational messages
- `WARNING`: Something unexpected, but still working
- `ERROR`: Error occurred but execution continues
- `CRITICAL`: Serious error, program may not continue

## Class Design Patterns

### Dataclasses for Configuration
Use `@dataclass` for configuration objects.

### Abstract Base Classes
Use `abc.ABC` and `@abstractmethod` for interfaces.

### Composition Over Inheritance
Prefer composition over deep inheritance hierarchies. Device classes compose functionality rather than inheriting from multiple specialized base classes.

## File Organization

### Package Structure
See `docs/directory_structure.md`.

### Configuration
All hardware configuration (COM ports, baud rates, timeouts) goes in `src/core/config.py`.

### Device Implementations
Device-specific implementations go in `src/devices/`.
- `base.py`: Base classes and abstract interfaces
- `brooks_mfc.py`: Brooks MFC implementation
- New devices follow naming pattern: `{vendor}_{device_type}.py`

### Tests
Test files go in `tests/` directory with matching structure:
- `test_brooks_mfc.py`
- Naming pattern: `test_{module_name}.py`

## PEP 8 Compliance

This project follows PEP 8 guidelines with the following specific notes:
- Line length: 88 characters (Ruff default)
- 4-space indentation
- PascalCase for classes, snake_case for functions/variables
- Avoid extraneous whitespace

## Tool Configuration

The project uses Ruff for linting. Ensure your editor is configured to:
- Use 4 spaces for indentation
- Trim trailing whitespace
- Use LF line endings (even on Windows)
- Set Python interpreter to `.venv/Scripts/python.exe`

See `.vscode/settings.json` for VSCode configuration.
