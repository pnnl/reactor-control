# Reactor Control System

A Python-based control system for laboratory reactors, supporting gas flow control, temperature management, and experimental automation.

## Features

- **Multi-device control**: Brooks Mass Flow Controllers (MFC), HPLC pumps, Omega CN7600 temperature controllers, MKS ToolWEB pressure monitoring
- **Three-layer architecture**: Devices → Operations → Experiments for clean separation of concerns
- **Experiment scripting**: Pythonic `ExperimentContext` API for running automated experiments
- **Gas concentration control**: MFC calibration with concentration-to-flow conversion
- **Safety interlocks**: Built-in safety checks and step logging
- **Data analysis**: Steady-state analysis with temperature correlation and visualization

## Architecture

```
┌─────────────────────────────────────┐
│        Experiments Layer            │  src/experiments/
│  (High-level experiment scripts)    │
└────────────────┬────────────────────┘
                 │
┌────────────────▼────────────────────┐
│        Operations Layer             │  src/operations/
│  (Process control, safety checks)   │
└────────────────┬────────────────────┘
                 │
┌────────────────▼────────────────────┐
│         Devices Layer               │  src/devices/
│  (Hardware communication drivers)    │
└─────────────────────────────────────┘
```

## Hardware

| Device | Model | Protocol |
|--------|-------|----------|
| Mass Flow Controller | Brooks 5850 series | RS-485 / Modbus |
| HPLC Pump | SSI | RS-232 |
| Temperature Controller | Omega CN7600 | RS-485 / Modbus |
| Pressure Monitor | MKS MG2000 | ToolWEB / Ethernet |

See `docs/architecture_overview.md` for full system design documentation.

## Installation

```bash
# Create virtual environment
python -m venv .venv
source .venv/Scripts/activate  # Windows
# source .venv/bin/activate    # Linux/macOS

# Install dependencies
pip install -e .
```

## Configuration

Device settings (COM ports, baud rates, addresses) are configured in `src/core/config.py`:

```python
DEVICE_CONFIG = {
    "hplc": {"port": "COM3", "baud_rate": 9600},
    "mfc": {"port": "COM4", "baud_rate": 19200, "address": 0x02},
    "omega": {"port": "COM5", "baud_rate": 9600},
    "mks_toolweb": {"host": "192.168.100.100", "port": 2000},
}
```

MFC calibration data is stored in `config/mfc_calibration.yaml`.

## Usage

### Running an Experiment

```python
from experiments.scripting import ExperimentContext

with ExperimentContext(sample_id="test-001") as ctx:
    ctx.set_sample(name="Test Sample", description="Calibration run")
    ctx.set_temperature(100.0, ramp_rate=5.0)
    ctx.hold(30)  # minutes
    ctx.set_gas_flows(
        flows={"NH3": 10.0, "NO": 5.0, "O2": 2.0},
        total_flow_rate=100.0,
        unit="ppm"
    )
    ctx.start_data_collection()
    ctx.hold(15)
    ctx.stop_data_collection()
    ctx.stop_all_flows()
```

### Device Control (Low-level)

```python
from devices.brooks_mfc import BrooksMFC

mfc = BrooksMFC(port="COM4", baud_rate=19200, address=0x02)
mfc.connect()
mfc.set_flow(50.0)  # SCCM
mfc.disconnect()
```

## Project Structure

```
reactor_control/
├── src/
│   ├── core/           # Configuration, logging, utilities
│   ├── devices/        # Hardware drivers
│   ├── operations/     # Control operations
│   └── experiments/    # Experiment management
├── tests/              # Unit tests
├── docs/               # Documentation
└── hardware_manuals/   # Device specifications
```

## Development

```bash
# Run tests
pytest tests/

# Lint code
ruff check src/

# Format code
ruff format src/
```

See `docs/project_status.md` for current development status.

## Safety

> **Warning**: This system controls physical instrumentation. Always verify hardware connections and safety interlocks before running experiments. Hardware tests should never be executed without explicit confirmation.
