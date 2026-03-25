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

### Experiment State Tracking & Measured Values Integration
**Implemented complete context in step logging with measured values from hardware:**

- **State variables added to `ExperimentContext`:**
  - `_current_temp_target` - Current temperature target
  - `_current_temp_actual` - Current measured temperature (from hardware)
  - `_current_ramp_rate` - Current ramp rate
  - `_current_hold_minutes` - Current hold duration
  - `_current_gas_flow_sccm` - Current total gas flow
  - `_current_gas_concentrations` - Current gas concentrations dict

- **`set_temperature()` now tracks state AND returns measured values:**
  - Updates `_current_temp_target`, `_current_ramp_rate`, `_current_temp_actual`, `_current_hold_minutes` at operation start
  - Returns actual measured temp via `result.data["temp_actual"]`
  - Polls temperature controller until stabilization

- **`set_gas_flows()` now tracks state AND reads back measured concentrations:**
  - Updates `_current_gas_flow_sccm` and `_current_gas_concentrations` at operation start
  - Reads actual concentrations from MFCs after setting flows
  - Polling logic: polls every 0.5s, waits for tolerance (±5%) AND two consecutive identical readings (< 0.1 diff)
  - Uses cylinder_concentration from calibration for SCCM → ppm conversion
  - Returns measured concentrations via `result.data["gas_concentrations"]`
  - Skips N2 (carrier gas) from output
  - Rounds values to 1 decimal place

- **`log_step()` automatically includes current state:**
  - Every logged step now includes `temp_target`, `temp_actual`, `ramp_rate`, `hold_minutes`, `gas_flow_sccm`, and `gas_concentrations`
  - This ensures downstream analysis has complete context for every step
  - No manual state tracking needed in experiment scripts

- **Modified APIs:**
  - `step_logger.py`: Added `sample_metadata` parameter, `gas_concentrations` dict field, removed obsolete fields
  - `brooks_mfc.py`: Renamed `get_flow_rate()` to `get_percent_open()` (clarifies it returns % not SCCM)
  - `flow_control.py`: Added `_read_gas_concentrations()` method with MFC polling and stabilization check
  - `scripting.py`: Removed `step_type` parameter from `log_step()` (always "state")
  - `experiments/steady_state.py`: Updated to use new API with combined temperature+hold calls

### Design Decision: Timeout Behavior
- `_read_gas_concentrations()` returns last read value on polling timeout
- Alternative considered but rejected: skip logging concentrations on timeout (loses data)
- Current approach: conservative fallback ensures no data gaps in logs

### Next Steps
1. Test the full implementation with hardware
2. Verify polling stability with real MFC responses
3. Consider if timeout threshold (default 60s) needs adjustment based on testing

---

## Session Memory - 2026-03-18

### Zero Drift Compensation for NH3
**Implemented offset-based correction for MFC reading drift at zero setpoint:**

- **Root Issue**: NH3 MFC reads ~0.2% when valve is closed (target 0%), causing erroneous non-zero ppm in JSON logs

- **Solution Design - Offset Parameter:**
  - Added `offset` field to `gas_routing_map` entries in `config/device_config.yaml`
  - NH3 configured with `offset: 0.2`
  - Offset represents the MFC drift value at zero flow

- **Implementation in `src/operations/flow_control.py` `_read_gas_concentrations()`:**
  - After MFC polling completes, retrieve offset from routing config
  - If `offset > 0` AND `actual_percent < 1.0%` threshold:
    - Subtract offset from reading: `actual_percent = max(0.0, actual_percent - offset)`
    - Example: 0.2% - 0.2% = 0.0%
    - Example: 0.25% - 0.2% = 0.05% (handles readings slightly above drift)
    - Floors at 0.0 using `max()` to prevent negative percentages

- **Why This Works:**
  - Compensates for known hardware drift without requiring policing logic
  - Applies only to readings below 1% (avoids affecting normal measurements)
  - Additive per-gas configuration allows different offsets for different channels if needed
  - Clean subtraction preserves readings above drift threshold

---

## Session Memory - 2026-03-24

### Data Visualization Module Created
**New `src/visualization/` package for processing and visualizing experiment data:**

- **`__init__.py`** - Package initialization with public API exports:
  - `ExperimentData` dataclass
  - `load_experiment_data()` main function
  - `load_ftir_data()`, `load_temperature_data()`, `load_experiment_steps()` individual loaders

- **`data_loader.py`** - Data loading and alignment module (314 lines):
  - `FTIR_COLUMNS` constant - Maps analyte names to column names in .prn files:
    - `no`: "NO (350,3000) 191C"
    - `no2`: "NO2 (150) 191C (1of2)"
    - `n2o`: "N2O (100,200,300) 191C (1of2)"
    - `nh3`: "NH3 (300) 191C (1of2)"
  - `_parse_ftir_datetime()` - Parses M/D/YYYY and HH:MM:SS.mmm timestamps
  - `_parse_csv_datetime()` - Parses ISO format timestamps
  - `load_ftir_data()` - Loads .prn files (tab-delimited with headers)
  - `load_temperature_data()` - Loads .csv files (datetime, target_temp, read_temp)
  - `load_experiment_steps()` - Loads .json experiment step records
  - `align_ftir_to_temperature()` - Aligns FTIR readings to nearest temperature reading
  - `load_experiment_data()` - High-level function loading all data with optional alignment

- **`ExperimentData` dataclass** - Container for aligned experiment data:
  - `ftir` - DataFrame with FTIR readings and parsed datetime
  - `temperature` - DataFrame with temperature log readings
  - `steps` - List of experiment step dictionaries
  - `experiment_id` - Experiment identifier
  - `sample_info` - Sample metadata (optional)

- **Sample data files in `src/visualization/`:**
  - `20260318_084229_steady-state.prn` - FTIR spectroscopy data (tab-delimited)
  - `20260318_084229_steady-state.csv` - Temperature log (datetime, target_temp, read_temp)
  - `20260318_084229_steady-state.json` - Experiment steps with sample metadata

---

## Session Memory - 2026-03-24 (Continued)

### Steady-State Analysis Refactoring
**Major reorganization of data analysis and visualization:**

- **`src/analyze/` package** - Data processing:
  - `data_loader.py` - File loading (PRN, CSV, JSON), temperature alignment
  - `analyze_ss.py` - Steady-state analysis:
    - `identify_isothermal_ranges()` - Finds isothermal periods (temp ±1.5°C for ≥15 min)
    - `get_steady_state_df()` - Extracts mean/std from last 10% of each range
    - `load_and_process()` - Loads experiment, processes, saves CSV, returns (df, path)
    - `_load_data_root()` - Reads data_root from config/paths.yaml
    - `IsothermalRange`, `SteadyStateValue` dataclasses

- **`src/visualization/` package** - Plotting only:
  - `plot_ss.py` - `plot_concentrations_vs_temperature()`, `plot_steady_state()`
  - `data_loader.py` removed (moved to analyze)

- **`src/experiments/steady_state.py`** - Clean entry point:
  - `run_steady_state()` - Runs experiment, calls `load_and_process()`, exports
  - Removed `main.py` (was launcher, no longer needed)

- **`src/experiments/_api.py`** - `_load_data_root()` already existed here

### Key API Design Decisions:
- `load_and_process(experiment_id, data_root=None, species=None, fraction=0.1)` 
  - Returns `(ss_df, output_path)` tuple
  - data_root defaults to None (loads from config internally)
  - Handles file loading, range detection, steady-state extraction, CSV save
- `plot_steady_state()` takes pre-processed ss_df, not raw ftir_df

### Data Format Reference:
- **PRN (FTIR)**: Tab-delimited, Date="M/D/YYYY", Time="HH:MM:SS.mmm"
- **CSV (Temperature)**: datetime="2026-03-18T08:48:12.255721", target_temp, read_temp
- **JSON (Steps)**: ISO timestamps, includes gas_concentrations, temp_target, temp_actual
