"""Temperature control operations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from typing import Callable
from typing import Optional
from typing import TYPE_CHECKING
import csv
import logging
import time
import sys

SRC_PATH = Path(__file__).resolve().parent.parent.parent
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from src.devices.omega_cn7600 import OmegaCN7600
from src.operations.base import BaseOperation
from src.operations.base import OperationResult
from src.operations.safety_interlocks import SafetyInterlocks


if TYPE_CHECKING:
    from .step_logger import StepLogger


logger = logging.getLogger(__name__)


@dataclass
class TemperatureStep:
    """Definition of a temperature program step."""

    target_temp: float
    ramp_rate: float
    hold_time_min: float


class TemperatureControl(BaseOperation):
    """Operations for managing temperature programs."""

    def __init__(
        self,
        controller: OmegaCN7600,
        safety_interlocks: Optional[SafetyInterlocks] = None,
        defaults: Optional[dict[str, Any]] = None,
        paths: Optional[dict[str, Any]] = None,
        step_logger: Optional[StepLogger] = None,
    ) -> None:
        super().__init__(
            name="TemperatureControl",
            defaults=defaults,
            paths=paths,
            step_logger=step_logger,
        )
        self.controller = controller
        self.safety_interlocks = safety_interlocks

    def run_temperature_program(
        self,
        target_temps: list[float],
        ramp_rates: list[float],
        hold_times: list[float],
        experiment_dir: Optional[Path] = None,
        poll_interval: Optional[float] = None,
        ramp_write_interval: Optional[float] = None,
        timeout: Optional[float] = None,
        abort_checker: Optional[Callable[[], bool]] = None,
    ) -> OperationResult:
        """Execute a multi-step temperature program.

        Args:
            target_temps: Target temperatures in °C.
            ramp_rates: Ramp rates in °C/min.
            hold_times: Hold durations in minutes.
            experiment_dir: Optional output directory override.
            poll_interval: Optional polling interval in seconds.
            timeout: Optional timeout in seconds.
            abort_checker: Optional callable to signal abort.

        Returns:
            OperationResult with success status.
        """

        if not target_temps:
            return OperationResult(
                success=False,
                message="Target temperatures list cannot be empty.",
                errors=["target_temps is empty."],
            )
        if not ramp_rates:
            return OperationResult(
                success=False,
                message="Ramp rates list cannot be empty.",
                errors=["ramp_rates is empty."],
            )
        if not hold_times:
            return OperationResult(
                success=False,
                message="Hold times list cannot be empty.",
                errors=["hold_times is empty."],
            )

        max_len = max(len(target_temps), len(ramp_rates), len(hold_times))
        target_temps = self._extend_list(target_temps, max_len)
        ramp_rates = self._extend_list(ramp_rates, max_len)
        hold_times = self._extend_list(hold_times, max_len)

        temperature_defaults = self.defaults.get("temperature_control", {})
        if not isinstance(temperature_defaults, dict):
            temperature_defaults = {}

        poll_interval = (
            poll_interval
            if poll_interval is not None
            else float(temperature_defaults.get("poll_interval", 5.0))
        )
        ramp_write_interval = (
            ramp_write_interval
            if ramp_write_interval is not None
            else float(temperature_defaults.get("ramp_write_interval", 2.0))
        )
        timeout = (
            timeout
            if timeout is not None
            else float(temperature_defaults.get("timeout", 3600.0))
        )

        if experiment_dir is None:
            experiment_dir = self.get_data_root()
        experiment_dir.mkdir(parents=True, exist_ok=True)
        now = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = experiment_dir / f"{now}_temperature_log.csv"

        if not self.controller.is_connected:
            if not self.controller.connect():
                return OperationResult(
                    success=False,
                    message="Temperature controller connection failed.",
                    errors=["Failed to connect to controller."],
                )

        steps = [
            TemperatureStep(target, ramp, hold)
            for target, ramp, hold in zip(target_temps, ramp_rates, hold_times)
        ]

        try:
            with log_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["datetime", "target_temp", "read_temp"])
                handle.flush()

                for step_index, step in enumerate(steps, start=1):
                    if self.safety_interlocks is not None:
                        ok, violations = self.safety_interlocks.check_all_targets(
                            target_temperature=step.target_temp,
                            ramp_rate=step.ramp_rate,
                        )
                        if not ok:
                            return OperationResult(
                                success=False,
                                message="Safety interlock violation.",
                                errors=violations,
                            )

                    if abort_checker and abort_checker():
                        return OperationResult(
                            success=False,
                            message="Temperature program aborted before step.",
                        )

                    ramp_result = self._apply_ramp(
                        writer,
                        handle,
                        step.target_temp,
                        step.ramp_rate,
                        ramp_write_interval,
                        abort_checker,
                    )
                    if not ramp_result:
                        self.log_step(
                            step_type="temperature",
                            step_number=step_index,
                            temp_target=step.target_temp,
                            ramp_rate=step.ramp_rate,
                            hold_time=step.hold_time_min,
                            status="failed",
                            error_message="Ramp aborted or failed.",
                        )
                        return OperationResult(
                            success=False,
                            message="Ramp aborted or failed.",
                        )

                    reached = self._wait_for_target(
                        writer=writer,
                        handle=handle,
                        target=step.target_temp,
                        poll_interval=poll_interval,
                        ramp_rate=step.ramp_rate,
                        abort_checker=abort_checker,
                    )
                    if not reached:
                        self.log_step(
                            step_type="temperature",
                            step_number=step_index,
                            temp_target=step.target_temp,
                            ramp_rate=step.ramp_rate,
                            hold_time=step.hold_time_min,
                            status="failed",
                            error_message="Failed to reach target.",
                        )
                        return OperationResult(
                            success=False,
                            message=f"Failed to reach target {step.target_temp}°C.",
                        )

                    duration_s = self._hold(
                        writer,
                        handle,
                        step.target_temp,
                        step.hold_time_min,
                        poll_interval,
                        abort_checker,
                    )
                    if duration_s is None:
                        return OperationResult(
                            success=False,
                            message="Aborted during hold period.",
                        )

                    self.log_step(
                        step_type="temperature",
                        step_number=step_index,
                        temp_target=step.target_temp,
                        ramp_rate=step.ramp_rate,
                        hold_time=step.hold_time_min,
                        duration_s=duration_s,
                        status="completed",
                    )

        except OSError as exc:
            return OperationResult(
                success=False,
                message="Failed to write temperature log.",
                errors=[str(exc)],
            )

        return OperationResult(success=True, message="Temperature program completed.")

    def set_temperature(
        self,
        target_temp: float,
        ramp_rate: Optional[float] = None,
        poll_interval: Optional[float] = None,
        ramp_write_interval: Optional[float] = None,
        abort_checker: Optional[Callable[[], bool]] = None,
    ) -> OperationResult:
        """Set a single temperature target without a program.

        Args:
            target_temp: Target temperature in °C.
            ramp_rate: Optional ramp rate in °C/min.
            poll_interval: Optional polling interval in seconds.
            ramp_write_interval: Optional setpoint write interval in seconds.
            abort_checker: Optional callable to signal abort.

        Returns:
            OperationResult with success status.
        """

        temperature_defaults = self.defaults.get("temperature_control", {})
        if not isinstance(temperature_defaults, dict):
            temperature_defaults = {}

        poll_interval = (
            poll_interval
            if poll_interval is not None
            else float(temperature_defaults.get("poll_interval", 5.0))
        )
        ramp_write_interval = (
            ramp_write_interval
            if ramp_write_interval is not None
            else float(temperature_defaults.get("ramp_write_interval", 2.0))
        )
        if ramp_rate is None:
            ramp_rate = float(temperature_defaults.get("default_ramp_rate", 10.0))

        if self.safety_interlocks is not None:
            ok, violations = self.safety_interlocks.check_all_targets(
                target_temperature=target_temp,
                ramp_rate=ramp_rate,
            )
            if not ok:
                return OperationResult(
                    success=False,
                    message="Safety interlock violation.",
                    errors=violations,
                )

        if not self.controller.is_connected:
            if not self.controller.connect():
                return OperationResult(
                    success=False,
                    message="Temperature controller connection failed.",
                    errors=["Failed to connect to controller."],
                )

        if not self._apply_ramp(
            writer=None,
            handle=None,
            target=target_temp,
            ramp_rate=ramp_rate,
            write_interval=ramp_write_interval,
            abort_checker=abort_checker,
        ):
            self.log_step(
                step_type="temperature",
                temp_target=target_temp,
                ramp_rate=ramp_rate,
                status="failed",
                error_message="Failed to apply setpoint ramp.",
            )
            return OperationResult(
                success=False,
                message="Failed to apply setpoint ramp.",
            )

        reached = self._wait_for_target(
            writer=None,
            handle=None,
            target=target_temp,
            poll_interval=poll_interval,
            ramp_rate=ramp_rate,
            abort_checker=abort_checker,
        )
        if not reached:
            self.log_step(
                step_type="temperature",
                temp_target=target_temp,
                ramp_rate=ramp_rate,
                status="failed",
                error_message="Failed to reach target temperature.",
            )
            return OperationResult(
                success=False,
                message="Failed to reach target temperature.",
            )

        self.log_step(
            step_type="temperature",
            temp_target=target_temp,
            ramp_rate=ramp_rate,
            status="completed",
        )

        # Read final temperature to return
        final_temp = self.controller.get_temperature()

        return OperationResult(
            success=True,
            message="Temperature setpoint reached.",
            data={"temp_actual": final_temp},
        )

    def _wait_for_target(
        self,
        writer: Any,
        handle: Any,
        target: float,
        poll_interval: float,
        ramp_rate: float,
        abort_checker: Optional[Callable[[], bool]],
    ) -> bool:
        """Wait until temperature reaches target within tolerance."""

        start_time = time.monotonic()
        last_print = start_time
        while True:
            if abort_checker and abort_checker():
                return False
            read_temp = self.controller.get_temperature()
            self._log_temperature(writer, handle, target, read_temp)
            last_print = self._print_heating_status(
                start_time,
                last_print,
                target,
                read_temp,
                target,
                ramp_rate,
            )
            if read_temp is not None:
                if abs(read_temp - target) <= 1.0:
                    return True
            time.sleep(poll_interval)

    def _apply_ramp(
        self,
        writer: Any,
        handle: Any,
        target: float,
        ramp_rate: float,
        write_interval: float,
        abort_checker: Optional[Callable[[], bool]],
    ) -> bool:
        """Apply a ramp by writing incremental setpoints.

        Args:
            writer: CSV writer for logging.
            target: Target temperature in °C.
            ramp_rate: Ramp rate in °C/min.
            write_interval: Interval between setpoint updates in seconds.
            abort_checker: Optional callable to signal abort.

        Returns:
            True if ramp sequence completes, False otherwise.
        """

        if write_interval <= 0:
            self.logger.error("Invalid ramp write interval.")
            return False
        if ramp_rate <= 0:
            return self.controller.set_setpoint(target)

        current_temp = self.controller.get_temperature()
        if current_temp is None:
            self.logger.error("Failed to read current temperature for ramp.")
            return False

        setpoints = self._build_ramp_setpoints(
            start_temp=current_temp,
            target_temp=target,
            ramp_rate=ramp_rate,
            write_interval=write_interval,
        )
        if not setpoints:
            return False

        start_time = time.monotonic()
        last_print = start_time
        for setpoint in setpoints:
            if abort_checker and abort_checker():
                return False
            if not self.controller.set_setpoint(setpoint):
                return False
            current_temp = self.controller.get_temperature()
            self._log_temperature(writer, handle, setpoint, current_temp)
            last_print = self._print_heating_status(
                start_time,
                last_print,
                target,
                current_temp,
                setpoint,
                ramp_rate,
            )
            time.sleep(write_interval)
        return True

    def _print_heating_status(
        self,
        start_time: float,
        last_print: float,
        target_temp: float,
        read_temp: Optional[float],
        write_temp: float,
        ramp_rate: float,
    ) -> float:
        """Print heating status every 30 seconds."""

        now = time.monotonic()
        if now - last_print < 30.0:
            return last_print
        elapsed_min = (now - start_time) / 60.0
        print(
            f"Elapsed Time: {elapsed_min:.2f} min\n"
            f"Target Temp: {target_temp} °C\n"
            f"Read Temp: {read_temp} °C\n"
            f"Write Temp: {write_temp} °C\n"
            f"Ramp Rate: {ramp_rate} °C/min\n"
        )
        return now

    def _build_ramp_setpoints(
        self,
        start_temp: float,
        target_temp: float,
        ramp_rate: float,
        write_interval: float,
    ) -> list[float]:
        """Build a list of incremental setpoints for a ramp.

        Args:
            start_temp: Starting temperature in °C.
            target_temp: Target temperature in °C.
            ramp_rate: Ramp rate in °C/min.
            write_interval: Interval between setpoint updates in seconds.

        Returns:
            List of setpoint temperatures.
        """

        delta = target_temp - start_temp
        if delta == 0:
            return [target_temp]

        step = ramp_rate * (write_interval / 60.0)
        if step <= 0:
            return []

        step = step if delta > 0 else -step
        setpoints: list[float] = []
        current = start_temp
        while (delta > 0 and current < target_temp) or (
            delta < 0 and current > target_temp
        ):
            current += step
            if delta > 0 and current > target_temp:
                current = target_temp
            if delta < 0 and current < target_temp:
                current = target_temp
            setpoints.append(round(current, 2))
        return setpoints

    def _hold(
        self,
        writer: Any,
        handle: Any,
        target: float,
        hold_time_min: float,
        poll_interval: float,
        abort_checker: Optional[Callable[[], bool]],
    ) -> Optional[float]:
        """Hold temperature for the specified duration."""

        duration_s = hold_time_min * 60.0
        start_time = time.monotonic()
        last_print = start_time
        while time.monotonic() - start_time < duration_s:
            if abort_checker and abort_checker():
                return None
            read_temp = self.controller.get_temperature()
            self._log_temperature(writer, handle, target, read_temp)
            last_print = self._print_heating_status(
                start_time,
                last_print,
                target,
                read_temp,
                target,
                0.0,
            )
            time.sleep(poll_interval)
        return duration_s

    def _log_temperature(
        self,
        writer: Any,
        handle: Any,
        target: float,
        read_temp: Optional[float],
    ) -> None:
        """Log a temperature reading to CSV."""

        if writer is None or handle is None:
            return
        timestamp = datetime.now().isoformat()
        writer.writerow([timestamp, f"{target:.2f}", read_temp])
        handle.flush()

    @staticmethod
    def _extend_list(values: list[float], target_len: int) -> list[float]:
        """Extend a list to the target length using the last value."""

        if len(values) >= target_len:
            return values
        extended = list(values)
        last_value = values[-1]
        extended.extend([last_value] * (target_len - len(values)))
        return extended


if __name__ == "__main__":
    # Example usage
    controller = OmegaCN7600()
    safety_interlocks = SafetyInterlocks()
    temp_control = TemperatureControl(controller, safety_interlocks)

    controller.connect()
    val = controller.get_temperature()  # read current temp
    print(f"Current Temperature: {val} °C")

    # temp_control.set_temperature(120)  # set single temp with defaults

    # result = temp_control.run_temperature_program(
    #      target_temps=[450, 400, 350, 300, 275, 250, 225, 200, 175, 150, 125, 100, 200],  # °C
    #      ramp_rates=[10.0],  # °C/min
    #      hold_times=[35.0, 35.0, 35.0, 35.0, 40.0, 40.0, 45.0, 50.0, 35.0, 35.0, 35.0, 35.0, 10.0],  # min
    #      experiment_dir=Path("C:\\Data\\nelson\\2026")
    #  )

    result = temp_control.run_temperature_program(
        target_temps=[120, 140, 160, 180, 200, 225, 250, 275, 300, 350, 400],  # °C
        ramp_rates=[10.0],  # °C/min
        hold_times=[30],  # min
        experiment_dir=Path("C:\\Data\\nelson\\2026"),
    )
