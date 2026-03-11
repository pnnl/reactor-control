"""Step logging for operations."""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Optional
import json
import logging
import sys


SRC_PATH = Path(__file__).resolve().parent.parent.parent
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))


logger = logging.getLogger(__name__)


@dataclass
class StepLogEntry:
    """Record for a single operation step.

    Args:
        step_number: Step sequence number.
        timestamp: ISO timestamp for the step.
        temp_target: Target temperature.
        temp_actual: Actual temperature.
        ramp_rate: Temperature ramp rate.
        hold_time: Hold duration in minutes.
        gas_concentrations: Gas concentrations as dict (e.g., {"h2": 9300.0, "no": 350.0}).
        gas_flow_sccm: Gas flow setpoint in SCCM.
        status: Status string.
        error_message: Optional error message.
    """

    step_number: int
    timestamp: str
    temp_target: Optional[float] = None
    temp_actual: Optional[float] = None
    ramp_rate: Optional[float] = None
    hold_time: Optional[float] = None
    gas_concentrations: Optional[dict] = None
    gas_flow_sccm: Optional[float] = None
    success: bool = False
    error_message: Optional[str] = None

    def to_dict(self) -> dict[str, object]:
        """Convert the entry to a dictionary.

        Returns:
            Dictionary representation of the entry.
        """

        return asdict(self)


class StepLogger:
    """Logger for experiment step records.

    Args:
        output_dir: Directory for log outputs.
        experiment_id: Experiment identifier.
        sample_id: Sample identifier.
        operator: Operator name.
    """

    def __init__(
        self,
        output_dir: Path,
        experiment_id: str,
        sample_id: str,
        operator: Optional[str] = None,
        output_filename: Optional[str] = None,
        sample_metadata: Optional[dict] = None,
    ) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.experiment_id = experiment_id
        self.sample_id = sample_id
        self.operator = operator or ""
        self.start_time = datetime.now()
        self.end_time: Optional[datetime] = None
        self._entries: list[StepLogEntry] = []
        self._step_counter = 0
        self._output_filename = output_filename or "step_log.json"
        self._sample_metadata = sample_metadata or {}
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def log_step(
        self,
        step_number: Optional[int] = None,
        temp_target: Optional[float] = None,
        temp_actual: Optional[float] = None,
        ramp_rate: Optional[float] = None,
        hold_time: Optional[float] = None,
        gas_concentrations: Optional[dict] = None,
        gas_flow_sccm: Optional[float] = None,
        success: bool = False,
        error_message: Optional[str] = None,
    ) -> StepLogEntry:
        """Log a step entry.

        Args:
            step_number: Optional override for step number.
            temp_target: Target temperature.
            temp_actual: Actual temperature.
            ramp_rate: Ramp rate in °C/min.
            hold_time: Hold time in minutes.
            gas_concentrations: Gas concentrations dict (measured values).
            gas_flow_sccm: Gas flow in SCCM.
            success: Whether the step was successful.
            error_message: Optional error message.

        Returns:
            StepLogEntry instance.
        """

        if step_number is None:
            self._step_counter += 1
            step_number = self._step_counter
        timestamp = datetime.now().isoformat()
        entry = StepLogEntry(
            step_number=step_number,
            timestamp=timestamp,
            temp_target=temp_target,
            temp_actual=temp_actual,
            ramp_rate=ramp_rate,
            hold_time=hold_time,
            gas_concentrations=gas_concentrations,
            gas_flow_sccm=gas_flow_sccm,
            success=success,
            error_message=error_message,
        )
        self._entries.append(entry)

        # Write immediately to file
        self._write_json()

        return entry

    def finalize(self) -> bool:
        """Finalize the log and write outputs.

        Returns:
            True if outputs were written, False otherwise.
        """

        self.end_time = datetime.now()
        return self._write_json()

    def _write_json(self) -> bool:
        """Write JSON log file.

        Returns:
            True if successful, False otherwise.
        """

        payload = {
            "experiment_id": self.experiment_id,
            "sample_id": self.sample_id,
            "operator": self.operator,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else "",
            "sample": self._sample_metadata,
            "steps": [entry.to_dict() for entry in self._entries],
        }
        output_path = self.output_dir / self._output_filename

        # Ensure output directory exists
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass

        try:
            with output_path.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
            return True
        except OSError as exc:
            self.logger.error(f"Failed to write JSON log: {exc}")
            return False


if __name__ == "__main__":
    logger = StepLogger(
        output_dir=Path("C:\\Data\\nelson\\test"),
        experiment_id="EXP-2026-001",
        sample_id="SAMPLE-A",
        operator="labuser",
    )

    logger.log_step(
        step_type="temperature_ramp",
        temp_target=150.0,
        temp_actual=25.0,
        ramp_rate=10.0,
        success=True,
    )

    success = logger.finalize()
    print(f"Output directory: {logger.output_dir}")
