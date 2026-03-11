# Development Environment

## Python Environment

- **Python Version:** >=3.14
- **Virtual Environment:** `.venv/`
- **Interpreter:** `.venv/Scripts/python.exe` (Windows)
- **Package Manager:** pip/uv (lock file: `uv.lock`)

## Project Structure

### Critical Paths
- **Source Code:** `src/`
- **Core Configuration:** `src/core/config.py` (COM ports, baud rates, timeouts)
- **Device Drivers:** `src/devices/`
  - Base classes: `devices/base.py`
  - Device implementations: `devices/brooks_mfc.py`
- **Tests:** `tests/`
- **Documentation:** `docs/`
- **Hardware Manuals:** `hardware_manuals/`

### Layer Architecture
- `devices/` - Hardware communication (bottom layer)
- `operations/` - Process orchestration (planned)
- `experiments/` - High-level procedures (planned)
- `core/` - Shared utilities (configuration, logging)

## Installation

```bash
# Install in development mode
pip install -e .

# Or with uv
uv sync
```

## Dependencies

**Core:**
- `numpy>=2.4.0`
- `pyserial>=3.5`

Add dependencies to `pyproject.toml`, then reinstall.

## Testing

Run tests from project root:
```bash
python tests/test_brooks_mfc.py
```

Test naming pattern: `test_{module_name}.py`

## Development Tools

- **Linter:** Ruff (uses default settings, 88 char line length)
- **Cache:** `.ruff_cache/`
- **Editor:** VS Code
  - Settings: `.vscode/settings.json`
  - Default interpreter: `.venv/Scripts/python.exe`

## Common Tasks

**Modify Hardware Settings:**
Edit `src/core/config.py`

**Add New Device:**
1. Create `src/devices/{vendor}_{device}.py`
2. Inherit from `SerialDevice` or `CommunicationProtocol`
3. Update `devices/__init__.py` `__all__` list
4. Add tests in `tests/`

**Add Dependency:**
1. Update `pyproject.toml`
2. Reinstall package

**Update Documentation:**
- Status: `docs/project_status.md`
- Structure: `docs/directory_structure.md`
- Workflow: `docs/development_workflow.md`
