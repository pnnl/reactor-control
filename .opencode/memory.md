## Session Memory - 2026-02-10

### Major Phase Restructuring
**Complete reorganization of the project phase plan to prioritize key communication protocols.**

#### New Phase Structure:
- **Phase 1:** Device Layer ✅ COMPLETE
- **Phase 2:** Operations Layer *(Planned)*
- **Phase 3:** Experiments Layer *(Planned)*
- **Phase 4:** Integration & Finalization *(Planned)*


---

## Outstanding Action Items (Do Not ACT or DELETE Unless Explicitly Requested)

- Bullet number 7 in .opencode/instructions.md needs to be updated as we proceed to Phase 2

---

## Session Memory - 2026-02-17

### Phase 2 (Operations Layer) Progress
- Implemented operations modules (base, step_logger, safety_interlocks, temperature_control, flow_control, sample_management, data_acquisition) and config scaffolding.
- Temperature control updated with ramp list generation (2s write interval default), CSV flush, 30s status prints during ramp/target/hold, and auto-extend of ramp/hold lists.
- Flow control now uses centralized gas routing (port/channel + H2O to HPLC) from src/core/config.py.
- Added optional default port handling in BrooksMFC/HPLCPump constructors.
- Added tests for non-hardware operations components.

### Notes
- Calibration file strategy for MFCs still pending design (format/location/mapping).

---

## Session Memory - 2026-02-23

### MFC Calibration Integration
**Implemented the full calibration integration system:**

- **Created `config/mfc_calibration.yaml`:**
  - YAML-based calibration data file
  - MFC calibrations keyed by port/channel
  - HPLC calibration included
  - Gas mapping to port/channel

- **Created `src/core/mfc_calibration.py`:**
  - Loads calibration data from YAML file
  - `CalibrationCurve` dataclass with accessors
  - `get_mfc_calibration()`, `get_gas_calibration()`, `get_hplc_calibration()` helpers
  - `reload_calibrations()` function for testing

- **Created `src/devices/calibration.py`:**
  - `CalibrationInterpolator` class with `interpolate_y(x)` and `interpolate_x(y)` methods

- **Updated `src/core/config.py`:**
  - Added `mfc_full_scale_sccm` dict for fallback linear scaling

- **Updated `src/operations/flow_control.py`:**
  - Added `_initialize_calibrations()` - loads interpolators from mfc_calibration config
  - Updated `_convert_sccm_to_percent()` - uses calibration when available
  - Added `_calculate_carrier_flow()` - derives N2 flow from `total_flow_rate`
  - Renamed parameter `total_flow_limit` → `total_flow_rate`

- **Updated `pyproject.toml`:**
  - Added `pyyaml>=6.0.0` dependency

### Config Directory Structure
```
config/
  mfc_calibration.yaml   # MFC and HPLC calibration data
```

### Usage Example
```python
# Auto-derive N2 carrier gas
flow_control.set_gas_flows(
    {"nh3": 4.9, "h2": 19.8, "o2": 21.1},  # N2 will be calculated
    total_flow_rate=410.0  # N2 = 410 - (4.9 + 19.8 + 21.1) = 364.2 sccm
)
```

## Session Memory - 2026-03-03

### MKS ToolWEB Integration
**Fixed MKS ToolWEB connectivity issues and MG2000 configuration:**

- **Root Cause**: MG2000 requires:
  1. TOOLWEB in addIns list
  2. Empty recipe field (recipe="")
  3. storePrn="TRUE"

- **Config Files Updated**:
  - Added `mg2000_ini_path` and `mg2000_mgrcp_path` to config
  - Both `config/device_config.yaml` and `src/core/config.py`

- **Key Discovery**: Empty sub_sensor works for all commands (not ETCH1)
  - Changed default in config from "ETCH1" to ""
  - Fixed `MKSToolWeb.connect()` to try empty first, then restore configured value

- **MG2000_last_used_recipe.MGRCP**: This is the active config file MG2000 uses
  - Added `[ToolWeb config]` section with IP-port, idle value settings
  - Updates both INI and MGRCP files

- **Simplified data_acquisition.py**:
  - Removed `sample_id` parameter (just uses experiment_name)
  - Removed `set_default_recipe` parameter
  - Removed `mks_data_subdir` - data goes directly to experiment_dir

- **Updated paths.yaml**: Removed mks_data_subdir

### Operations Modules
- Added `if __main__` entry points to:
  - `step_logger.py` - JSON-only logging
  - `sample_management.py` - Sample creation demo
  - `safety_interlocks.py` - Safety limit tests

- Fixed sample_management.py: Removed mks_data_subdir reference

---

## Session Memory - 2026-02-25

### Flow Control Refinements
**Fixed device connection and channel handling in flow control operations:**

- **Fixed `stop_all_flows()` method:**
  - Connects to each MFC device before setting flow to 0 (was referencing undefined `device` variable)
  - Iterates through `gas_routing_map` to get port and channel for each gas
  - Uses `_resolve_mfc_by_port()` to find the correct MFC device
  - Calls `set_flow_rate(0.0, channel=channel)` with explicit channel parameter
  - Connects to HPLC pump, sets flow to 0, then stops pump

- **Enhanced water (H2O) handling in `set_gas_concentrations()`:**
  - Added check: if h2o flow is 0, just stop the pump instead of calling `inverse_predict(0)`
  - Prevents mathematical errors when water concentration is 0

**Key Pattern**: Both `set_gas_concentrations()` and `stop_all_flows()` now properly:
- Iterate through `gas_routing_map` to find device locations
- Connect devices before sending commands
- Use explicit channel parameters
- Handle edge cases (0 flow for water)

---

## Session Memory - 2026-03-10

### Experiment State Tracking
**Implemented complete context in step logging:**

- **State variables added to `ExperimentContext`:**
  - `_current_temp_target` - Current temperature target
  - `_current_ramp_rate` - Current ramp rate
  - `_current_gas_flow_sccm` - Current total gas flow
  - `_current_gas_concentrations` - Current gas concentrations dict

- **`set_temperature()` now tracks state:**
  - Updates `_current_temp_target` and `_current_ramp_rate` at start of method

- **`set_gas_flows()` now tracks state:**
  - Updates `_current_gas_flow_sccm` and `_current_gas_concentrations` at start of method

- **`log_step()` automatically includes current state:**
  - Every logged step now includes `temp_target`, `ramp_rate`, `gas_flow_sccm`, and `gas_concentrations`
  - This ensures downstream analysis has complete context for every step

- **Changed `gas_type` to `gas_concentrations` dict:**
  - Better for downstream parsing
  - Full gas specification in each step
