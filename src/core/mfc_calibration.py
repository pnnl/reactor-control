"""MFC and HPLC calibration data configuration.

This module loads calibration curves for all mass flow controllers
and the HPLC pump from the YAML config file and fits linear regressions.

Calibration Format:
- MFC channels: x = % open setting, y = flow in SCCM
- HPLC pump: x = flow in mL/min, y = response in %

Linear fit: flow (sccm) = m * percent + b
To convert: percent = (flow - b) / m
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml


# Config file path
CONFIG_DIR = Path(__file__).parent.parent.parent / "config"
MFC_CALIBRATION_FILE = CONFIG_DIR / "mfc_calibration.yaml"


# ============================================================================
# Linear Regression Utilities
# ============================================================================


@dataclass
class LinearFit:
    """Linear fit result: y = m * x + b"""

    m: float  # slope
    intercept: float  # intercept
    r_squared: float  # goodness of fit

    def predict(self, x: float) -> float:
        """Predict y given x."""
        return self.m * x + self.intercept

    def inverse_predict(self, y: float) -> float:
        """Given y, solve for x: x = (y - intercept) / m"""
        return (y - self.intercept) / self.m


def _fit_linear(x: List[float], y: List[float]) -> LinearFit:
    """Fit a linear regression to calibration data.

    Args:
        x: Input values (e.g., % open)
        y: Output values (e.g., flow in sccm)

    Returns:
        LinearFit with slope (m), intercept, and R² value
    """
    import numpy as np

    x_arr = np.array(x)
    y_arr = np.array(y)

    # Fit linear regression: y = m*x + b
    coeffs = np.polyfit(x_arr, y_arr, 1)
    m, b = coeffs

    # Calculate R²
    y_pred = m * x_arr + b
    ss_res = np.sum((y_arr - y_pred) ** 2)
    ss_tot = np.sum((y_arr - np.mean(y_arr)) ** 2)
    r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0

    return LinearFit(m=float(m), intercept=float(b), r_squared=float(r_squared))


# ============================================================================
# Calibration Curve
# ============================================================================


@dataclass
class CalibrationCurve:
    """Represents a calibration curve with linear fit.

    Attributes:
        gas_name: Human-readable gas name (e.g., "NH3", "H2")
        x_values: Raw input values (e.g., % open for MFC)
        y_values: Raw output values (e.g., SCCM for MFC)
        x_unit: Unit string for x values
        y_unit: Unit string for y values
        cylinder_concentration: Concentration of gas in cylinder (ppm or %)
        concentration_unit: Unit of cylinder_concentration ("ppm" or "percent")
        fit: Pre-computed linear fit (y = m*x + b)
    """

    gas_name: str
    x_values: List[float]
    y_values: List[float]
    x_unit: str = "% open"
    y_unit: str = "sccm"
    cylinder_concentration: float = None
    concentration_unit: str = None
    fit: Optional[LinearFit] = None

    def __post_init__(self):
        """Compute linear fit after initialization."""
        if self.fit is None and len(self.x_values) >= 2:
            self.fit = _fit_linear(self.x_values, self.y_values)

    def sccm_to_percent(self, sccm: float) -> float:
        """Convert flow in SCCM to percent setting.

        Uses inverse of linear fit: percent = (sccm - b) / m
        """
        if self.fit is None:
            raise ValueError("No linear fit available")
        return self.fit.inverse_predict(sccm)

    def percent_to_sccm(self, percent: float) -> float:
        """Convert percent setting to flow in SCCM.

        Uses linear fit: sccm = m * percent + b
        """
        if self.fit is None:
            raise ValueError("No linear fit available")
        return self.fit.predict(percent)

    def concentration_to_flow(
        self, concentration: float, total_flow: float, concentration_unit: str = "ppm"
    ) -> float:
        """Convert desired concentration to gas flow in SCCM.

        Args:
            concentration: Target concentration in the gas mixture
            total_flow: Total gas flow in SCCM
            concentration_unit: Unit of target concentration ("ppm" or "percent")

        Returns:
            Required gas flow in SCCM

        Calculation:
            - Convert target to fraction: frac = concentration / 1,000,000 (ppm) or / 100 (%)
            - Required flow: flow = total_flow * frac_actual / frac_cylinder
            - Where frac_cylinder = cylinder_concentration / 1,000,000 (ppm) or / 100 (%)
        """
        # Convert cylinder concentration to fraction
        if self.concentration_unit == "ppm":
            cylinder_frac = self.cylinder_concentration / 1_000_000.0
        else:  # percent
            cylinder_frac = self.cylinder_concentration / 100.0

        if cylinder_frac <= 0:
            raise ValueError(
                f"Invalid cylinder concentration: {self.cylinder_concentration}"
            )

        # Convert target concentration to fraction
        if concentration_unit == "ppm":
            target_frac = concentration / 1_000_000.0
        else:  # percent
            target_frac = concentration / 100.0

        # Calculate required gas flow
        # flow * cylinder_frac = total_flow * target_frac
        # flow = total_flow * target_frac / cylinder_frac
        required_flow = total_flow * target_frac / cylinder_frac

        return required_flow


# ============================================================================
# YAML Loading
# ============================================================================


def _load_yaml_config() -> dict:
    """Load calibration data from YAML file."""
    if not MFC_CALIBRATION_FILE.exists():
        raise FileNotFoundError(f"Calibration file not found: {MFC_CALIBRATION_FILE}")

    with open(MFC_CALIBRATION_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# Cache for loaded calibrations
_mfc_calibrations: Optional[Dict[Tuple[str, int], CalibrationCurve]] = None
_gas_calibrations: Optional[Dict[str, CalibrationCurve]] = None
_hplc_calibration: Optional[CalibrationCurve] = None
_default_concentration_units: Dict[str, str] = {}


def _initialize_calibrations() -> None:
    """Load calibrations from YAML file."""
    global \
        _mfc_calibrations, \
        _gas_calibrations, \
        _hplc_calibration, \
        _default_concentration_units

    if _mfc_calibrations is not None:
        return  # Already initialized

    config = _load_yaml_config()

    # Load MFC calibrations
    _mfc_calibrations = {}
    for cal in config.get("mfc_calibrations", []):
        port = cal["port"]
        channel = cal["channel"]

        # Get cylinder concentration - stored as ppm internally
        cylinder_conc = cal.get("cylinder_concentration")

        # Determine if cylinder is in ppm or percent (stored in YAML comment mostly)
        # For now, assume all cylinder concentrations are in the unit specified
        # We'll normalize to ppm: if percent, multiply by 10000
        conc_unit = cal.get("concentration_unit", "ppm")
        if conc_unit == "percent":
            cylinder_conc = cylinder_conc * 10000.0  # Convert percent to ppm

        curve = CalibrationCurve(
            gas_name=cal["gas_name"],
            x_values=cal["x_values"],
            y_values=cal["y_values"],
            x_unit=cal.get("x_unit", "% open"),
            y_unit=cal.get("y_unit", "sccm"),
            cylinder_concentration=cylinder_conc,  # Always stored as ppm
            concentration_unit="ppm",  # Internal storage is always ppm
        )
        _mfc_calibrations[(port, channel)] = curve

    # Load default concentration units for user requests
    global _default_concentration_units
    _default_concentration_units = config.get("default_concentration_units", {})

    # Load gas mapping and create gas name lookup
    _gas_calibrations = {}
    gas_mapping = config.get("gas_mapping", {})
    for gas_name, location in gas_mapping.items():
        if location == "hplc":
            continue
        port, channel = location
        if (port, channel) in _mfc_calibrations:
            _gas_calibrations[gas_name] = _mfc_calibrations[(port, channel)]

    # Load HPLC calibration
    hplc_config = config.get("hplc_calibration")
    if hplc_config:
        _hplc_calibration = CalibrationCurve(
            gas_name=hplc_config["gas_name"],
            x_values=hplc_config["x_values"],
            y_values=hplc_config["y_values"],
            x_unit=hplc_config.get("x_unit", "mL/min"),
            y_unit=hplc_config.get("y_unit", "%"),
        )
        _gas_calibrations["h2o"] = _hplc_calibration


# Module-level initialization
_initialize_calibrations()


# ============================================================================
# Public API
# ============================================================================


def get_mfc_calibration(port: str, channel: int) -> CalibrationCurve | None:
    """Get MFC calibration by port and channel."""
    if _mfc_calibrations is None:
        _initialize_calibrations()
    return _mfc_calibrations.get((port, channel))


def get_gas_calibration(gas_name: str) -> CalibrationCurve | None:
    """Get calibration for a gas by name."""
    if _gas_calibrations is None:
        _initialize_calibrations()
    return _gas_calibrations.get(gas_name.lower())


def get_hplc_calibration() -> CalibrationCurve | None:
    """Get HPLC pump calibration."""
    if _hplc_calibration is None:
        _initialize_calibrations()
    return _hplc_calibration


def get_default_concentration_unit(gas_name: str) -> str:
    """Get the default concentration unit for a gas.

    Args:
        gas_name: Name of the gas (e.g., "nh3", "o2")

    Returns:
        "ppm" or "percent"
    """
    if _default_concentration_units is None:
        _initialize_calibrations()
    return _default_concentration_units.get(gas_name.lower(), "ppm")


def reload_calibrations() -> None:
    """Force reload of calibration data from YAML file."""
    global _mfc_calibrations, _gas_calibrations, _hplc_calibration
    _mfc_calibrations = None
    _gas_calibrations = None
    _hplc_calibration = None
    _initialize_calibrations()
