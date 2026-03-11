"""Safety interlocks for operations layer."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from typing import Optional
from typing import TYPE_CHECKING
import logging
import sys

SRC_PATH = Path(__file__).resolve().parent.parent.parent
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from .base import BaseOperation
from src.devices.brooks_mfc import BrooksMFC
from src.devices.hplc_pump import HPLCPump
from src.devices.omega_cn7600 import OmegaCN7600


if TYPE_CHECKING:
    from .step_logger import StepLogger


logger = logging.getLogger(__name__)


@dataclass
class SafetyLimits:
    """Safety limit configuration values.

    Args:
        max_temperature: Maximum allowable temperature in °C.
        max_total_flow: Maximum total gas flow in SCCM.
        min_carrier_flow: Minimum carrier gas flow in SCCM.
        max_ramp_rate: Maximum allowable ramp rate in °C/min.
        max_water_flow: Maximum allowable water flow in mL/min.
    """

    max_temperature: float = 800.0
    max_total_flow: float = 1000.0
    min_carrier_flow: float = 0.0
    max_ramp_rate: float = 50.0
    max_water_flow: float = 102.50

    @classmethod
    def from_defaults(cls, defaults: dict[str, object]) -> "SafetyLimits":
        """Create limits from defaults dictionary.

        Args:
            defaults: Defaults dictionary.

        Returns:
            SafetyLimits instance.
        """

        values = defaults.get("safety_limits", {}) if isinstance(defaults, dict) else {}
        if not isinstance(values, dict):
            values = {}
        return cls(
            max_temperature=float(values.get("max_temperature", cls.max_temperature)),
            max_total_flow=float(values.get("max_total_flow", cls.max_total_flow)),
            min_carrier_flow=float(
                values.get("min_carrier_flow", cls.min_carrier_flow)
            ),
            max_ramp_rate=float(values.get("max_ramp_rate", cls.max_ramp_rate)),
            max_water_flow=float(values.get("max_water_flow", cls.max_water_flow)),
        )


class SafetyInterlocks(BaseOperation):
    """Safety checks for operations.

    Args:
        limits: Optional safety limits override.
        temperature_controller: Optional Omega CN7600 device.
        mfc_devices: Optional list of Brooks MFC devices.
        hplc_pump: Optional HPLC pump.
    """

    def __init__(
        self,
        limits: Optional[SafetyLimits] = None,
        temperature_controller: Optional[OmegaCN7600] = None,
        mfc_devices: Optional[list[BrooksMFC]] = None,
        hplc_pump: Optional[HPLCPump] = None,
        defaults: Optional[dict[str, Any]] = None,
        paths: Optional[dict[str, Any]] = None,
        step_logger: Optional[StepLogger] = None,
    ) -> None:
        super().__init__(
            name="SafetyInterlocks",
            defaults=defaults,
            paths=paths,
            step_logger=step_logger,
        )
        self.limits = limits or SafetyLimits.from_defaults(self.defaults)
        self.temperature_controller = temperature_controller
        self.mfc_devices = mfc_devices or []
        self.hplc_pump = hplc_pump

    def check_temperature(self, target: float) -> tuple[bool, Optional[str]]:
        """Check target temperature against safety limits.

        Args:
            target: Target temperature in °C.

        Returns:
            Tuple of (is_safe, violation_message).
        """

        if target > self.limits.max_temperature:
            return (
                False,
                f"Target temperature {target}°C exceeds max {self.limits.max_temperature}°C",
            )
        return True, None

    def check_flow(self, total_sccm: float) -> tuple[bool, Optional[str]]:
        """Check total flow against safety limits.

        Args:
            total_sccm: Total flow in SCCM.

        Returns:
            Tuple of (is_safe, violation_message).
        """

        if total_sccm > self.limits.max_total_flow:
            return (
                False,
                f"Total flow {total_sccm} SCCM exceeds max {self.limits.max_total_flow} SCCM",
            )
        return True, None

    def check_ramp_rate(self, ramp_rate: float) -> tuple[bool, Optional[str]]:
        """Check ramp rate against safety limits.

        Args:
            ramp_rate: Ramp rate in °C/min.

        Returns:
            Tuple of (is_safe, violation_message).
        """

        if ramp_rate > self.limits.max_ramp_rate:
            return (
                False,
                f"Ramp rate {ramp_rate}°C/min exceeds max {self.limits.max_ramp_rate}°C/min",
            )
        return True, None

    def check_water_flow(self, flow_ml_min: float) -> tuple[bool, Optional[str]]:
        """Check water flow against safety limits.

        Args:
            flow_ml_min: Water flow in mL/min.

        Returns:
            Tuple of (is_safe, violation_message).
        """

        if flow_ml_min > self.limits.max_water_flow:
            return (
                False,
                f"Water flow {flow_ml_min} mL/min exceeds max {self.limits.max_water_flow} mL/min",
            )
        return True, None

    def check_carrier_flow(self, flow_sccm: float) -> tuple[bool, Optional[str]]:
        """Check carrier gas flow against minimum limits.

        Args:
            flow_sccm: Carrier gas flow in SCCM.

        Returns:
            Tuple of (is_safe, violation_message).
        """

        if flow_sccm < self.limits.min_carrier_flow:
            return (
                False,
                f"Carrier flow {flow_sccm} SCCM below min {self.limits.min_carrier_flow} SCCM",
            )
        return True, None

    def check_all_targets(
        self,
        target_temperature: Optional[float] = None,
        total_flow_sccm: Optional[float] = None,
        ramp_rate: Optional[float] = None,
        water_flow_ml_min: Optional[float] = None,
        carrier_flow_sccm: Optional[float] = None,
    ) -> tuple[bool, list[str]]:
        """Check all provided targets against safety limits.

        Args:
            target_temperature: Target temperature in °C.
            total_flow_sccm: Total gas flow in SCCM.
            ramp_rate: Ramp rate in °C/min.
            water_flow_ml_min: Water flow in mL/min.
            carrier_flow_sccm: Carrier gas flow in SCCM.

        Returns:
            Tuple of (is_safe, list of violation messages).
        """

        violations: list[str] = []

        if target_temperature is not None:
            ok, message = self.check_temperature(target_temperature)
            if not ok and message:
                violations.append(message)

        if total_flow_sccm is not None:
            ok, message = self.check_flow(total_flow_sccm)
            if not ok and message:
                violations.append(message)

        if ramp_rate is not None:
            ok, message = self.check_ramp_rate(ramp_rate)
            if not ok and message:
                violations.append(message)

        if water_flow_ml_min is not None:
            ok, message = self.check_water_flow(water_flow_ml_min)
            if not ok and message:
                violations.append(message)

        if carrier_flow_sccm is not None:
            ok, message = self.check_carrier_flow(carrier_flow_sccm)
            if not ok and message:
                violations.append(message)

        return len(violations) == 0, violations

    def emergency_shutdown(self) -> bool:
        """Attempt to stop all connected devices safely.

        Returns:
            True if all shutdown commands succeed, False otherwise.
        """

        success = True

        if self.temperature_controller is not None:
            result = self.temperature_controller.set_safe_temperature()
            success = success and result

        for device in self.mfc_devices:
            result = device.set_flow_rate(0.0)
            success = success and result

        if self.hplc_pump is not None:
            if not self.hplc_pump.set_flow_rate(0.0):
                success = False
            if not self.hplc_pump.stop_pump():
                success = False

        return success


if __name__ == "__main__":
    interlocks = SafetyInterlocks()

    print("Testing safety limits...")
    print(f"Max Temperature: {interlocks.limits.max_temperature}°C")
    print(f"Max Total Flow: {interlocks.limits.max_total_flow} SCCM")
    print(f"Max Ramp Rate: {interlocks.limits.max_ramp_rate}°C/min")
    print(f"Max Water Flow: {interlocks.limits.max_water_flow} mL/min")

    print("\n--- Test 1: Temperature within limits ---")
    ok, msg = interlocks.check_temperature(150.0)
    print(f"Check 150°C: {'PASS' if ok else 'FAIL'} {msg or ''}")

    print("\n--- Test 2: Temperature exceeds limit ---")
    ok, msg = interlocks.check_temperature(900.0)
    print(f"Check 900°C: {'PASS' if ok else 'FAIL'} {msg or ''}")

    print("\n--- Test 3: Flow within limits ---")
    ok, msg = interlocks.check_flow(500.0)
    print(f"Check 500 SCCM: {'PASS' if ok else 'FAIL'} {msg or ''}")

    print("\n--- Test 4: Flow exceeds limit ---")
    ok, msg = interlocks.check_flow(1500.0)
    print(f"Check 1500 SCCM: {'PASS' if ok else 'FAIL'} {msg or ''}")

    print("\n--- Test 5: Ramp rate within limits ---")
    ok, msg = interlocks.check_ramp_rate(10.0)
    print(f"Check 10°C/min: {'PASS' if ok else 'FAIL'} {msg or ''}")

    print("\n--- Test 6: Ramp rate exceeds limit ---")
    ok, msg = interlocks.check_ramp_rate(100.0)
    print(f"Check 100°C/min: {'PASS' if ok else 'FAIL'} {msg or ''}")

    print("\n--- Test 7: Water flow within limits ---")
    ok, msg = interlocks.check_water_flow(50.0)
    print(f"Check 50 mL/min: {'PASS' if ok else 'FAIL'} {msg or ''}")

    print("\n--- Test 8: Water flow exceeds limit ---")
    ok, msg = interlocks.check_water_flow(150.0)
    print(f"Check 150 mL/min: {'PASS' if ok else 'FAIL'} {msg or ''}")

    print("\n--- Test 9: Check all targets (all valid) ---")
    ok, msgs = interlocks.check_all_targets(
        target_temperature=200.0,
        total_flow_sccm=300.0,
        ramp_rate=5.0,
        water_flow_ml_min=10.0,
    )
    print(f"All checks valid: {'PASS' if ok else 'FAIL'}")
    if msgs:
        print(f"Violations: {msgs}")

    print("\n--- Test 10: Check all targets (multiple violations) ---")
    ok, msgs = interlocks.check_all_targets(
        target_temperature=900.0,
        total_flow_sccm=2000.0,
        ramp_rate=100.0,
        water_flow_ml_min=150.0,
    )
    print(f"All checks valid: {'PASS' if ok else 'FAIL'}")
    if msgs:
        print(f"Violations: {msgs}")
