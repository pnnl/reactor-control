"""Flow control operations for gases and liquids."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from typing import Optional
from typing import Callable
from typing import TYPE_CHECKING
import csv
import logging
import time
import sys

SRC_PATH = Path(__file__).resolve().parent.parent.parent
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from src.core.config import default_config
from src.core.mfc_calibration import (
    get_gas_calibration,
    get_hplc_calibration,
    get_default_concentration_unit,
)
from src.devices.brooks_mfc import BrooksMFC
from src.devices.hplc_pump import HPLCPump
from src.operations.base import BaseOperation
from src.operations.base import OperationResult
from src.operations.safety_interlocks import SafetyInterlocks


if TYPE_CHECKING:
    from .step_logger import StepLogger


logger = logging.getLogger(__name__)


@dataclass
class FlowCalibrationPoint:
    """Calibration point for SCCM to percent mapping."""

    sccm: float
    percent: float


class FlowControl(BaseOperation):
    """Operations for managing gas and liquid flows."""

    def __init__(
        self,
        mfc_devices: list[BrooksMFC],
        hplc_pump: Optional[HPLCPump] = None,
        safety_interlocks: Optional[SafetyInterlocks] = None,
        gas_id_map: Optional[dict[str, int]] = None,
        calibration_files: Optional[dict[str, str]] = None,
        defaults: Optional[dict[str, Any]] = None,
        paths: Optional[dict[str, Any]] = None,
        step_logger: Optional[StepLogger] = None,
    ) -> None:
        super().__init__(
            name="FlowControl",
            defaults=defaults,
            paths=paths,
            step_logger=step_logger,
        )
        flow_defaults = self.defaults.get("flow_control", {})
        if not isinstance(flow_defaults, dict):
            flow_defaults = {}
        self.mfc_devices = mfc_devices
        self.hplc_pump = hplc_pump
        self.safety_interlocks = safety_interlocks
        self.total_flow_limit = float(flow_defaults.get("total_flow_limit", 410.0))
        default_gas_id_map = flow_defaults.get("gas_id_map", {})
        if gas_id_map is not None:
            self.gas_id_map = gas_id_map
        elif isinstance(default_gas_id_map, dict):
            self.gas_id_map = {}
            for key, value in default_gas_id_map.items():
                if not isinstance(value, (int, str)):
                    continue
                try:
                    self.gas_id_map[str(key)] = int(value)
                except (TypeError, ValueError):
                    self.logger.error(f"Invalid gas ID value for {key}: {value}")
        else:
            self.gas_id_map = {}
        default_calibrations = flow_defaults.get("calibration_files", {})
        self.calibration_files = (
            calibration_files
            if calibration_files is not None
            else (
                default_calibrations if isinstance(default_calibrations, dict) else {}
            )
        )
        self.last_water_flow_rate: Optional[float] = None

    def set_gas_concentrations(
        self,
        gas_concentrations: dict[str, float],
        total_flow_rate: Optional[float] = None,
        experiment_dir: Optional[Path] = None,
    ) -> OperationResult:
        """Set gas concentrations using Brooks MFC devices.

        Args:
            gas_concentrations: Mapping of gas name to concentration.
                - Most gases: ppm (e.g., nh3, h2, no)
                - O2 and H2O: percent (e.g., 21.0 for air)
            total_flow_rate: Optional total flow rate.
                If provided and n2 is not in gas_concentrations, carrier gas
                (N2) will be automatically calculated to achieve this total.
                Note: water (h2o) is not included in total flow calculation.
            experiment_dir: Optional directory for flow_config output.

        Returns:
            OperationResult indicating success.
        """

        if not gas_concentrations:
            return OperationResult(
                success=False,
                message="No gas concentrations specified.",
                errors=["gas_concentrations is empty."],
            )

        # Separate MFC gases from HPLC water
        mfc_gases = {}
        h2o_concentration = None

        for gas_name, concentration in gas_concentrations.items():
            if gas_name.lower() == "h2o":
                h2o_concentration = concentration
            else:
                mfc_gases[gas_name] = concentration

        # Convert MFC gas concentrations to flows
        gas_flows = {}
        for gas_name, concentration in mfc_gases.items():
            unit = get_default_concentration_unit(gas_name)

            flow_sccm = self._convert_concentration_to_flow(
                gas_name, concentration, unit, total_flow_rate or 100.0
            )
            if flow_sccm is None:
                return OperationResult(
                    success=False,
                    message=f"Failed to convert concentration for {gas_name}.",
                )
            gas_flows[gas_name] = flow_sccm

        # Add water to gas_flows for total flow calculation
        if h2o_concentration is not None:  # and h2o_concentration != 0.0:
            hplc_cal = get_hplc_calibration()

            if (
                hplc_cal is not None
                and hplc_cal.fit is not None
                and h2o_concentration != 0
            ):
                target_frac = h2o_concentration / 100.0
                water_flow = total_flow_rate * target_frac
            else:
                water_flow = 0.0

            gas_flows["h2o"] = water_flow

        # Calculate total flow for validation (including water)
        total_flow = 0.0
        for gas_name, flow_sccm in gas_flows.items():
            total_flow += flow_sccm

        # Handle carrier gas derivation if total_flow_rate is specified
        if total_flow_rate is not None and "n2" not in gas_flows:
            gas_flows = self._calculate_carrier_flow(gas_flows, total_flow_rate)

        limit = self.total_flow_limit
        if total_flow > limit:
            return OperationResult(
                success=False,
                message="Total flow exceeds limit.",
                errors=[f"Total flow {total_flow} SCCM exceeds limit {limit} SCCM."],
            )

        if self.safety_interlocks is not None:
            ok, violations = self.safety_interlocks.check_all_targets(
                total_flow_sccm=total_flow,
            )
            if not ok:
                return OperationResult(
                    success=False,
                    message="Safety interlock violation.",
                    errors=violations,
                )

        # write flow values
        for gas_name, flow_sccm in gas_flows.items():
            if flow_sccm < 0:
                return OperationResult(
                    success=False,
                    message=f"Invalid flow for {gas_name}.",
                    errors=["Flow rates must be non-negative."],
                )
            routing = default_config.gas_routing_map.get(gas_name)
            if routing is None:
                return OperationResult(
                    success=False,
                    message=f"No routing entry for gas {gas_name}.",
                )

            device_type = routing.get("device")
            if device_type == "hplc":
                if flow_sccm == 0:
                    result = self._set_hplc_flow(0.0)
                else:
                    water_flow_mlmin = hplc_cal.fit.inverse_predict(flow_sccm)
                    result = self._set_hplc_flow(water_flow_mlmin)
                if not result.success:
                    return OperationResult(
                        success=False,
                        message=f"Failed to set water flow for {gas_name}.",
                        errors=result.errors,
                    )
                continue

            if device_type != "mfc":
                return OperationResult(
                    success=False,
                    message=f"Unsupported device type for gas {gas_name}.",
                )

            port_value = routing.get("port")
            channel_value = routing.get("channel", 1)
            if isinstance(channel_value, str):
                try:
                    channel_value = int(channel_value)
                except ValueError:
                    channel_value = None
            if not isinstance(channel_value, int):
                return OperationResult(
                    success=False,
                    message=f"Invalid MFC channel for gas {gas_name}.",
                )
            if not isinstance(port_value, str) or not port_value:
                return OperationResult(
                    success=False,
                    message=f"Invalid MFC port for gas {gas_name}.",
                )

            port_value = routing.get("port")
            device = self._resolve_mfc_by_port(port_value)
            if device is None:
                return OperationResult(
                    success=False,
                    message=f"No MFC device for gas {gas_name}.",
                )

            percent = self._convert_sccm_to_percent(gas_name, flow_sccm)
            if percent is None:
                return OperationResult(
                    success=False,
                    message=f"Failed to convert flow for {gas_name}.",
                )

            if not device.is_connected:
                if not device.connect():
                    return OperationResult(
                        success=False,
                        message=f"Failed to connect MFC for gas {gas_name}.",
                    )

            if not device.set_flow_rate(percent, channel=channel_value):
                return OperationResult(
                    success=False,
                    message=f"Failed to set flow for {gas_name}.",
                )

        # Read back actual concentrations
        actual_concentrations = self._read_gas_concentrations(
            gas_flows, total_flow_rate
        )

        return OperationResult(
            success=True,
            message="Gas flows set.",
            data={"gas_concentrations": actual_concentrations},
        )

    def _read_gas_concentrations(
        self, gas_flows: dict[str, float], total_flow: float
    ) -> dict[str, float]:
        """Read actual gas concentrations from MFCs.

        Polls the MFC until the read value is within tolerance of the set value,
        or until timeout (10 seconds).

        Args:
            gas_flows: Dictionary of gas flows that were set.
            total_flow: Total flow rate in SCCM.

        Returns:
            Dictionary of actual concentration values by gas name.
        """
        actual_concentrations = {}
        offset = None

        # Polling parameters
        max_wait_seconds = 20.0
        poll_interval = 2  # seconds between polls
        tolerance_percent = 1.0  # ±1% of target is acceptable

        for gas_name, flow_sccm in gas_flows.items():
            routing = default_config.gas_routing_map.get(gas_name)
            if routing is None:
                continue

            device_type = routing.get("device")
            if device_type == "hplc":
                hplc_cal = get_hplc_calibration()
                if self.hplc_pump is not None and self.hplc_pump.is_connected:
                    val = hplc_cal.fit.predict(self.last_water_flow_rate)
                    actual_concentrations[gas_name] = round(max(val/total_flow * 100, 0.0), 1)
                continue

            if device_type != "mfc":
                continue

            # Skip carrier gas (N2) - not needed in output
            if gas_name.lower() == "n2":
                continue
            if gas_name.lower() == "nh3" or gas_name.lower() == "h2":
                offset = routing.get('offset', 0.2)

            port_value = routing.get("port")
            channel_value = routing.get("channel", 1)
            if isinstance(channel_value, str):
                try:
                    channel_value = int(channel_value)
                except ValueError:
                    continue

            device = self._resolve_mfc_by_port(port_value)
            if device is None or not device.is_connected:
                continue

            # Calculate target percent for this gas (for tolerance comparison)
            target_percent = round(
                self._convert_sccm_to_percent(gas_name, flow_sccm), 1
            )
            if target_percent is None:
                target_percent = 0.0

            # Poll until stable (two consecutive identical readings) or timeout
            actual_percent = None
            last_percent = None
            stable_count = 0
            start_time = time.monotonic()
            while time.monotonic() - start_time < max_wait_seconds:
                # Get actual percent open from MFC
                actual_percent = device.get_percent_open(channel=channel_value)
                if actual_percent is None:
                    time.sleep(poll_interval)
                    continue

                # Check for two consecutive identical readings (within tolerance)
                if target_percent > 0:
                    diff_percent = (
                        abs(actual_percent - target_percent) / target_percent * 100
                    )
                    if diff_percent <= tolerance_percent:
                        if (
                            last_percent is not None
                            and abs(actual_percent - last_percent) < 0.1
                        ):
                            stable_count += 1
                            if stable_count >= 2:
                                break
                        else:
                            stable_count = 0
                    else:
                        stable_count = 0
                elif actual_percent <= 1.0:  # Close to zero
                    if (
                        last_percent is not None
                        and abs(actual_percent - last_percent) == 0.0
                    ):
                        stable_count += 1
                        if stable_count >= 2:
                            break
                    else:
                        stable_count = 0
                else:
                    stable_count = 0

                last_percent = actual_percent
                time.sleep(poll_interval)

            if offset and actual_percent < (offset + 0.1):
                actual_percent = float(max(0, actual_percent - offset))
                actual_concentrations[gas_name] = round(actual_percent, 1)
                continue

            # Convert percent open to SCCM
            cal_curve = get_gas_calibration(gas_name)
            concentration_unit = get_default_concentration_unit(gas_name)

            try:
                if cal_curve is not None and cal_curve.fit is not None:
                    # Convert percent to SCCM using calibration
                    actual_sccm = cal_curve.percent_to_sccm(actual_percent)
                    # Get cylinder concentration for conversion
                    cylinder_conc = getattr(cal_curve, "cylinder_concentration", None)
                else:
                    # Fallback: linear conversion using full scale
                    full_scale = default_config.mfc_full_scale_sccm.get(
                        port_value, 200.0
                    )
                    actual_sccm = (
                        (actual_percent / 100.0) * full_scale if full_scale > 0 else 0.0
                    )
                    cylinder_conc = None

                # Convert SCCM to concentration (ppm or percent)
                if concentration_unit == "ppm" and cylinder_conc:
                    # For ppm: use cylinder concentration to convert SCCM to ppm
                    # concentration = (actual_sccm / total_flow) * cylinder_concentration
                    if total_flow and total_flow > 0:
                        concentration = (actual_sccm / total_flow) * cylinder_conc
                    else:
                        concentration = 0.0
                    actual_concentrations[gas_name] = round(concentration, 1)
                else:
                    actual_percent = (
                        (actual_sccm / total_flow) * cylinder_conc * (100 / 1e6)
                    )
                    actual_concentrations[gas_name] = round(actual_percent, 1)

            except Exception as e:
                self.logger.warning(f"Failed to convert flow for {gas_name}: {e}")
                continue

        return actual_concentrations

    def set_standby_flow(self) -> OperationResult:
        """Stop all gas and water flows safely, keeping carrier gas (n2) at 10%.

        Returns:
            OperationResult indicating success.
        """

        success = True
        for gas_name, routing in default_config.gas_routing_map.items():
            if routing.get("device") != "mfc":
                continue

            port = routing.get("port")
            channel = routing.get("channel", 1)

            if isinstance(channel, str):
                try:
                    channel = int(channel)
                except ValueError:
                    self.logger.warning(
                        f"Invalid channel {channel} for {gas_name}, using 1"
                    )
                    channel = 1

            device = self._resolve_mfc_by_port(port)
            if device is None:
                self.logger.error(f"No MFC device for port {port}")
                continue

            if not device.is_connected:
                if not device.connect():
                    self.logger.error(f"Failed to connect MFC on {port}")
                    success = False
                    continue

            if gas_name.lower() == "n2":
                flow_rate = 10.0
                self.logger.info(f"Setting carrier gas {gas_name} to {flow_rate}%")
            elif gas_name.lower() == "o2":
                flow_rate = 5.0
                self.logger.info(f"Setting {gas_name} to {flow_rate}% for standby")
            else:
                flow_rate = 0.0

            if not device.set_flow_rate(flow_rate, channel=channel):
                self.logger.error(
                    f"Failed to set flow on {gas_name} (channel {channel})"
                )
                success = False

        if self.hplc_pump is not None:
            if not self.hplc_pump.is_connected:
                if not self.hplc_pump.connect():
                    self.logger.error("Failed to connect HPLC pump")
                    success = False

            if not self.hplc_pump.stop_pump():
                success = False

        status = "completed" if success else "failed"
        self.log_step(step_type="stop_flows", status=status)

        if success:
            return OperationResult(success=True, message="All flows stopped.")
        return OperationResult(success=False, message="Failed to stop all flows.")

    def _set_hplc_flow(
        self,
        water_flow_rate: float,
        microbore: bool = True,
    ) -> OperationResult:
        """Set water flow using the HPLC pump.

        Args:
            water_flow_rate: Flow rate in mL/min.
            microbore: Whether to use microbore scaling.

        Returns:
            OperationResult indicating success.
        """

        if self.hplc_pump is None:
            return OperationResult(
                success=False,
                message="No HPLC pump configured.",
            )

        if water_flow_rate < 0:
            return OperationResult(
                success=False,
                message="Water flow must be non-negative.",
            )

        if self.safety_interlocks is not None:
            ok, violations = self.safety_interlocks.check_all_targets(
                water_flow_ml_min=water_flow_rate,
            )
            if not ok:
                return OperationResult(
                    success=False,
                    message="Safety interlock violation.",
                    errors=violations,
                )

        if not self.hplc_pump.is_connected:
            if not self.hplc_pump.connect():
                return OperationResult(
                    success=False,
                    message="Failed to connect HPLC pump.",
                )

        if water_flow_rate == 0.0:
            if not self.hplc_pump.stop_pump():
                return OperationResult(
                    success=False,
                    message="Failed to stop HPLC pump.",
                )
        else:
            if not self.hplc_pump.set_flow_rate(water_flow_rate, microbore=microbore):
                return OperationResult(
                    success=False,
                    message="Failed to set water flow.",
                )
            if not self.hplc_pump.run_pump():
                return OperationResult(
                    success=False,
                    message="Failed to start HPLC pump.",
                )

        self.last_water_flow_rate = water_flow_rate

        self.log_step(
            step_type="water_flow",
            water_flow_ml_min=water_flow_rate,
            status="completed",
        )

        return OperationResult(success=True, message="Water flow set.")

    def _resolve_mfc_by_port(self, port: str) -> Optional[BrooksMFC]:
        """Resolve MFC device by port."""
        for device in self.mfc_devices:
            if device.port == port:
                return device
        self.logger.error(f"No MFC device configured for port: {port}")
        return None

    def _convert_sccm_to_percent(
        self, gas_name: str, flow_sccm: float
    ) -> Optional[float]:
        """Convert SCCM flow to percent based on calibration or full scale.

        Uses linear regression from calibration data.
        """
        # Use calibration if available
        cal_curve = get_gas_calibration(gas_name)
        if cal_curve is not None and cal_curve.fit is not None:
            try:
                percent = cal_curve.sccm_to_percent(flow_sccm)
                return max(0.0, min(100.0, percent))
            except Exception as e:
                self.logger.warning(
                    f"Calibration conversion failed for {gas_name}: {e}, falling back to linear."
                )

        # Fallback to linear scaling using mfc_full_scale_sccm from config
        port = default_config.gas_routing_map.get(gas_name, {}).get("port")
        if port:
            full_scale = default_config.mfc_full_scale_sccm.get(port, 200.0)
        else:
            full_scale = 200.0  # Default

        if full_scale <= 0:
            self.logger.error("Invalid MFC full scale configuration.")
            return None
        percent = (flow_sccm / full_scale) * 100.0
        return max(0.0, min(100.0, percent))

    def _convert_concentration_to_flow(
        self,
        gas_name: str,
        concentration: float,
        concentration_unit: str,
        total_flow: float,
    ) -> Optional[float]:
        """Convert concentration to flow in SCCM.

        Args:
            gas_name: Name of the gas (e.g., "nh3", "o2")
            concentration: Target concentration (ppm or percent)
            concentration_unit: Unit of concentration ("ppm" or "percent")
            total_flow: Total gas flow in SCCM

        Returns:
            Required gas flow in SCCM, or None on error
        """
        cal_curve = get_gas_calibration(gas_name)
        if cal_curve is None:
            self.logger.error(f"No calibration found for gas: {gas_name}")
            return None

        try:
            flow_sccm = cal_curve.concentration_to_flow(
                concentration, total_flow, concentration_unit
            )
            return max(0.0, flow_sccm)
        except Exception as e:
            self.logger.error(f"Failed to convert concentration for {gas_name}: {e}")
            return None

    def _calculate_carrier_flow(
        self, gas_flows: dict[str, float], total_flow_rate: float
    ) -> dict[str, float]:
        """Calculate carrier gas (N2) flow to achieve total flow rate.

        Args:
            gas_flows: Dictionary of gas flows (excluding carrier n2)
            total_flow_rate: Desired total flow rate in SCCM

        Returns:
            Updated gas_flows dict including carrier gas (n2)
        """
        # Sum of all gases except carrier (n2) - including water
        process_gases = {k: v for k, v in gas_flows.items() if k.lower() != "n2"}
        current_total = sum(process_gases.values())

        carrier_flow = total_flow_rate - current_total

        if carrier_flow < 0:
            self.logger.warning(
                f"Carrier gas flow would be negative ({carrier_flow}). Setting to 0."
            )
            carrier_flow = 0.0

        # Add carrier gas to flows
        result = dict(process_gases)
        result["n2"] = carrier_flow

        return result


if __name__ == "__main__":
    # Example usage
    mfc = [BrooksMFC("COM4"), BrooksMFC("COM5")]
    hplc = HPLCPump()
    safety_interlocks = SafetyInterlocks()
    flow_control = FlowControl(mfc, hplc, safety_interlocks)

    # # Set gas concentrations (ppm for most, percent for O2)
    # result = flow_control.set_gas_concentrations(
    #     {
    #         "h2": 0.0,  # ppm
    #         "nh3": 0.0,  # ppm
    #         "no": 0.0,  # ppm
    #         "o2": 10.0,  # percent
    #         "h2o": 6.0,  # percent
    #     },
    #     total_flow_rate=380,  # sccm total flow
    #     experiment_dir=Path("C:\\Data\\nelson\\2026"),
    # )

    flow_control.set_standby_flow()
