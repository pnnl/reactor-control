# Reactor Control System

A Python-based control system for laboratory reactors, supporting gas flow control, temperature management, and experimental automation.

## Features

- **Multi-device control**: Brooks Mass Flow Controllers (MFC), HPLC pumps, Omega CN7600 temperature controllers, MKS ToolWEB pressure monitoring
- **Three-layer architecture**: Devices → Operations → Experiments for clean separation of concerns
- **Experiment scripting**: Pythonic `Experiment` API for running automated experiments
- **Gas concentration control**: MFC calibration with concentration-to-flow conversion
- **Safety interlocks**: HPLC temperature checks, built-in safety checks and step logging
- **Data analysis**: Steady-state analysis with conversion/selectivity calculations

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
from src.experiments import Experiment, Sample

exp = Experiment(name="steady-state", connect_devices=True)
exp.set_sample(Sample(
    batch_id="sample-001",
    mass_mg=50.0,
    operator="labuser",
    composition="Pd/Al2O3",
    metal="Pd",
    support="g-Al2O3",
    metal_loading_wt_percent=0.1,
    mesh_size="30-60",
    synthesis_method="incipient wetness",
))

# Pretreatment with multiple steps
exp = pretreatment(
    exp=exp,
    target_temps=[650, 400],
    ramp_rates=[10.0],
    hold_times=[240, 30],
    gas_flows=[
        {"total_flow_rate": None, "gas_concentrations": {"h2": 9300.0, "nh3": 0.0, "no": 0.0, "o2": 0.0, "h2o": 0.0}},
        {"total_flow_rate": 410, "gas_concentrations": {"h2": 9300.0, "nh3": 0.0, "no": 350.0, "o2": 0.0, "h2o": 20.0}},
    ],
)

# Steady-state experiment
exp = run_steady_state(
    exp=exp,
    target_temps=[120, 140, 160],
    ramp_rates=[10.0],
    hold_times=[30.0],
    gas_flow={
        "total_flow_rate": 410,
        "gas_concentrations": {"h2": 9300.0, "nh3": 0.0, "no": 350.0, "o2": 0.0, "h2o": 20.0},
    },
)

exp.standby()
```

### Device Control (Low-level)

```python
from src.devices.brooks_mfc import BrooksMFC

mfc = BrooksMFC(port="COM4", config=DeviceConfig())
mfc.connect()
mfc.set_flow_rate(50.0)  # SCCM
mfc.disconnect()
```

## Project Structure

```
reactor_control/
├── src/
│   ├── analyze/       # Data analysis
│   ├── config/        # Configuration files
│   ├── core/          # Configuration, logging, utilities
│   ├── devices/       # Hardware drivers
│   ├── operations/    # Control operations
│   └── experiments/   # Experiment management
├── tests/             # Unit tests
├── docs/              # Documentation
└── hardware_manuals/  # Device specifications
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
