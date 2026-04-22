"""Experiment API for reactor control.

Provides an Experiment class for writing flexible experiment scripts.

Example:
    from src.experiments import Experiment, Sample

    exp = Experiment(name="my-experiment", connect_devices=False)
    try:
        exp.set_sample(Sample(...))
        exp.set_gas_flows(total_flow_rate=410, gas_concentrations={...})
        exp.start_data_collection()
        exp.hold(minutes=5.0)
    finally:
        exp.close()
"""

from __future__ import annotations

import logging
import shutil
import time
import yaml
from dataclasses import asdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from typing import Optional

from src.operations.data_acquisition import DataAcquisition
from src.operations.flow_control import FlowControl
from src.operations.sample_management import SampleManager
from src.operations.safety_interlocks import SafetyInterlocks
from src.operations.step_logger import StepLogger
from src.operations.temperature_control import TemperatureControl


logger = logging.getLogger(__name__)


def _load_data_root() -> Path:
    """Load the data root path from config."""

    paths_file = Path(__file__).resolve().parent.parent.parent / "config" / "paths.yaml"
    if paths_file.exists():
        try:
            with paths_file.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                root = data.get("data_root")
                if root:
                    return Path(root)
        except Exception:
            pass
    return Path("C:/Data")

def _load_cloud_root() -> Path:
    """Load the cloud root path from config."""

    paths_file = Path(__file__).resolve().parent.parent.parent / "config" / "paths.yaml"
    if paths_file.exists():
        try:
            with paths_file.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                root = data.get("cloud_storage")
                if root:
                    return Path(root)
        except Exception:
            pass
    return Path("Z:/we43712")

@dataclass
class Sample:
    """Sample information for an experiment."""

    batch_id: str
    mass_mg: float
    operator: str
    composition: str
    metal: str
    support: str
    metal_loading_wt_percent: float
    mesh_size: str
    is_new_sample: bool
    synthesis_method: str


class Experiment:
    """Class for running experiments.

    Example:
        exp = Experiment(name="my-experiment", connect_devices=False)
        try:
            exp.set_sample(Sample(...))
            exp.set_gas_flows(...)
        finally:
            exp.close()
    """

    def __init__(
        self,
        name: str = "",
        output_dir: Optional[Path] = None,
        connect_devices: bool = False,
        defaults: Optional[dict[str, Any]] = None,
    ) -> None:
        """Initialize the experiment."""
        self.name = name
        self.output_dir = output_dir
        self.connect_devices = connect_devices
        self.defaults = defaults
        self.sample: Optional[Sample] = None

        # Internal state
        self._experiment_id: Optional[str] = None
        self._experiment_dir: Optional[Path] = None
        self._start_time: Optional[datetime] = None
        self._temperature_control: Optional[TemperatureControl] = None
        self._flow_control: Optional[FlowControl] = None
        self._data_acquisition: Optional[DataAcquisition] = None
        self._safety_interlocks: Optional[SafetyInterlocks] = None
        self._step_logger: Optional[StepLogger] = None
        self._is_running: bool = False
        self._finished: bool = False  # Track if finish was logged

        # Track current state for step logging
        self._current_temp_target: Optional[float] = None
        self._current_temp_actual: Optional[float] = None
        self._current_ramp_rate: Optional[float] = None
        self._current_hold_minutes: Optional[float] = None
        self._current_gas_flow_sccm: Optional[float] = None
        self._current_gas_concentrations: dict = {}
        self._mks_on: bool = False
        self.ss_ranges: list = []

        # Set up logging
        self._logger = logging.getLogger(f"{__name__}.Experiment")
        self._setup_logging()
        self.start()

    def _setup_logging(self) -> None:
        """Configure logging for the experiment."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in self.name)
        self._experiment_id = f"{timestamp}_{safe_name}"

        if self.output_dir is None:
            data_root = _load_data_root()
            self.output_dir = data_root
        self._experiment_dir = self.output_dir

        try:
            self._experiment_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self._logger.warning(f"Could not create experiment dir: {exc}")
            self._experiment_dir = Path(".")

        log_file = f"{self._experiment_dir / self._experiment_id}.log"
        try:
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(
                logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
            )
            self._logger.addHandler(file_handler)
        except OSError as exc:
            self._logger.warning(f"Could not create log file: {exc}")

    def start(self) -> None:
        """Start the experiment."""
        self._start_time = datetime.now()
        self._is_running = True
        self._logger.info(f"=== Experiment Started: {self.name} ===")

    def close(self) -> None:
        """Close the experiment and cleanup resources."""
        if not self._finished:
            self._finished = True
            self._is_running = False

            if self._temperature_control is not None:
                try:
                    if hasattr(self._temperature_control, "controller"):
                        self._temperature_control.controller.disconnect()
                except Exception as exc:
                    self._logger.warning(
                        f"Error disconnecting temperature control: {exc}"
                    )

            if self._flow_control is not None:
                try:
                    for mfc in self._flow_control.mfc_devices:
                        if hasattr(mfc, "disconnect"):
                            mfc.disconnect()
                    if self._flow_control.hplc_pump is not None:
                        if hasattr(self._flow_control.hplc_pump, "disconnect"):
                            self._flow_control.hplc_pump.disconnect()
                except Exception as exc:
                    self._logger.warning(f"Error disconnecting flow control: {exc}")

            if self._data_acquisition is not None:
                try:
                    if hasattr(self._data_acquisition, "toolweb"):
                        self._data_acquisition.toolweb.disconnect()
                except Exception as exc:
                    self._logger.warning(f"Error disconnecting data acquisition: {exc}")

            self._logger.info(f"=== Experiment Finished: {self.name} ===")

    def __del__(self) -> None:
        """Cleanup when the instance is deleted."""
        self.close()

    # =========================================================================
    # Atomic Operations
    # =========================================================================

    def set_sample(self, sample: Sample) -> None:
        """Set the sample information."""
        self.sample = sample
        sample_metadata = asdict(sample)
        self._step_logger = StepLogger(
            output_dir=self._experiment_dir,
            experiment_id=self._experiment_id,
            operator=sample.operator,
            output_filename=f"{self._experiment_id}.json",
            sample_metadata=sample_metadata,
        )

    def log_step(self, message: Optional[str] = None) -> None:
        """Log a progress step."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        if message:
            self._logger.info(f"[{timestamp}] {message}")

        # Read actual temperature from hardware if not already set
        if self._current_temp_actual is None:
            self._ensure_temperature_control()
            if self._temperature_control is not None:
                controller = self._temperature_control.controller
                # Ensure connection before reading
                if not controller.is_connected:
                    controller.connect()
                try:
                    self._current_temp_actual = controller.get_temperature()
                except Exception:
                    pass  # Keep as None if read fails

        if self._step_logger is not None:
            self._step_logger.log_step(
                success=True,
                temp_target=self._current_temp_target,
                temp_actual=self._current_temp_actual,
                ramp_rate=self._current_ramp_rate,
                hold_time=self._current_hold_minutes,
                gas_flow_sccm=self._current_gas_flow_sccm,
                gas_concentrations=self._current_gas_concentrations
                if self._current_gas_concentrations
                else None,
                mks_on=self._mks_on,
            )

    def set_temperature(
        self,
        target: float,
        rate: Optional[float] = None,
        hold_minutes: Optional[float] = None,
        log_step: bool = False,
    ) -> None:
        """Set the temperature."""
        self._current_temp_target = target
        self._current_ramp_rate = rate
        self._current_hold_minutes = hold_minutes

        self._ensure_temperature_control()

        if self._temperature_control is None:
            self._logger.warning(
                f"Mock set_temperature: target={target}°C, rate={rate}°C/min"
            )
            if hold_minutes is not None:
                self.hold(
                    minutes=hold_minutes,
                    description=f"Temp stabilization at {target}°C",
                )
            if log_step:
                self.log_step()
            return

        rate_str = f" at {rate}°C/min" if rate else ""
        self._logger.info(f"Setting temperature: {target}°C{rate_str}")

        log_path = (
            self._experiment_dir / f"{self._experiment_id}.csv"
            if self._experiment_dir
            else None
        )
        result = self._temperature_control.set_temperature(
            target, ramp_rate=rate, log_path=log_path
        )
        if result.success:
            self._logger.info("Temperature set successfully")
            if result.data and "temp_actual" in result.data:
                self._current_temp_actual = result.data["temp_actual"]
            if log_step:
                self.log_step()
        else:
            self._logger.warning(f"Failed to set temperature: {result.message}")

        if hold_minutes is not None:
            self.hold(
                minutes=hold_minutes, description=f"Temp stabilization at {target}°C"
            )

    def run_temperature_program(
        self,
        target_temps: list[float],
        ramp_rates: list[float],
        hold_times: list[float],
        log_steps: bool = False,
    ) -> bool:
        """Run a multi-step temperature program."""
        self._ensure_temperature_control()

        if self._temperature_control is None:
            self._logger.warning(
                f"Mock run_temperature_program: {len(target_temps)} steps"
            )
            for i, target in enumerate(target_temps):
                self._current_temp_target = target
                self._current_ramp_rate = (
                    ramp_rates[i] if i < len(ramp_rates) else ramp_rates[-1]
                )
                self._current_hold_minutes = (
                    hold_times[i] if i < len(hold_times) else hold_times[-1]
                )
                self._logger.info(
                    f"Step {i + 1}: Mock temp {target}°C at {self._current_ramp_rate}°C/min, "
                    f"hold {self._current_hold_minutes} min"
                )
                hold_time = hold_times[i] if i < len(hold_times) else hold_times[-1]
                if hold_time > 0:
                    self.hold(minutes=hold_time, description=f"Mock hold at {target}°C")
                if log_steps:
                    self.log_step(
                        message=f"Completed temperature step {i + 1}/{len(target_temps)}"
                    )
            return True

        self._logger.info(f"Running temperature program with {len(target_temps)} steps")
        log_path = (
            self._experiment_dir / f"{self._experiment_id}.csv"
            if self._experiment_dir
            else None
        )
        result = self._temperature_control.run_temperature_program(
            target_temps=target_temps,
            ramp_rates=ramp_rates,
            hold_times=hold_times,
            log_path=log_path,
        )

        if result.success:
            self._logger.info("Temperature program completed successfully")
            if target_temps:
                self._current_temp_target = target_temps[-1]
                self._current_ramp_rate = ramp_rates[-1] if ramp_rates else None
                self._current_hold_minutes = hold_times[-1] if hold_times else None
                if hasattr(self._temperature_control, "controller"):
                    self._current_temp_actual = (
                        self._temperature_control.controller.get_temperature()
                    )
            self.ss_ranges = result.data.get("ss_ranges", []) if result.data else []
            return True
        else:
            self._logger.warning(f"Temperature program failed: {result.message}")
            return False

    def hold(self, minutes: float, description: Optional[str] = None) -> None:
        """Hold/pause for a duration."""
        desc = description or "hold"
        self._logger.info(f"Holding for {minutes} min: {desc}")
        print(f"[HOLD] {minutes} min - {desc}")
        time.sleep(minutes * 60)

    def set_gas_flows(
        self,
        total_flow_rate: float,
        gas_concentrations: dict[str, float],
        log_step: bool = False,
    ) -> None:
        """Set gas flows."""
        self._current_gas_flow_sccm = total_flow_rate
        self._current_gas_concentrations = dict(gas_concentrations)

        self._ensure_flow_control()

        if self._flow_control is None:
            self._logger.warning(f"Mock set_gas_flows: total={total_flow_rate} SCCM")
            if log_step:
                self.log_step()
            return

        if "h2o" in gas_concentrations and gas_concentrations["h2o"] > 0:
            is_safe, error_msg, current_temp = (
                self._flow_control.check_hplc_safe_temperature()
            )
            if not is_safe:
                if current_temp is not None and self._safety_interlocks:
                    safe_temp = self._safety_interlocks.limits.max_hplc_temperature
                    self._logger.warning(
                        f"Temperature {current_temp}°C below HPLC limit. "
                        f"Heating to {safe_temp}°C..."
                    )
                    self._ensure_temperature_control()
                    if self._temperature_control:
                        self._temperature_control.set_temperature(
                            safe_temp, ramp_rate=0
                        )

        self._logger.info(f"Setting gas flows: {total_flow_rate} SCCM total")
        for gas, value in gas_concentrations.items():
            self._logger.info(f"  {gas}: {value}")

        result = self._flow_control.set_gas_concentrations(
            gas_concentrations=gas_concentrations,
            total_flow_rate=total_flow_rate,
            experiment_dir=self._experiment_dir,
        )

        if result.success:
            self._logger.info("Gas flows set successfully")
            if result.data and "gas_concentrations" in result.data:
                self._current_gas_concentrations = result.data["gas_concentrations"]
            if log_step:
                self.log_step()
        else:
            self._logger.warning(f"Failed to set gas flows: {result.errors}")

    def standby(self, temperature: float = 120.0) -> None:
        """Stop all flows and set temperature to standby."""
        if self._flow_control is not None:
            try:
                self._flow_control.set_standby_flow()
            except Exception as exc:
                self._logger.warning(f"Error stopping flows: {exc}")

        if self._temperature_control is not None:
            try:
                self._temperature_control.set_temperature(temperature)
                self._logger.info(
                    f"Temperature control set to standby ({temperature}C)"
                )
            except Exception as exc:
                self._logger.warning(f"Error stopping temperature control: {exc}")

        if self._data_acquisition is not None:
            try:
                self._data_acquisition.stop_recording()
            except Exception as exc:
                self._logger.warning(f"Error stopping data collection: {exc}")

        if self._step_logger is not None:
            self._step_logger.finalize()

        if self._start_time:
            duration = (datetime.now() - self._start_time).total_seconds()
            self._logger.info(f"Total experiment duration: {duration:.1f} seconds")

    def start_data_collection(
        self, interval_sec: float = 5.0, log_step: bool = True
    ) -> None:
        """Start data collection."""
        self._ensure_data_acquisition()

        if self._data_acquisition is None:
            self._logger.warning(
                f"Mock start_data_collection: interval={interval_sec}s"
            )
            return

        self._logger.info(f"Starting data collection: {interval_sec}s interval")
        result = self._data_acquisition.start_recording(
            experiment_name=self._experiment_id,
            data_directory=str(self._experiment_dir),
        )

        if result.success:
            self._mks_on = True
            self._logger.info("Data collection started")
            if log_step:
                self.log_step()
        else:
            self._logger.warning(f"Failed to start data collection: {result.message}")

    def stop_data_collection(self, log_step: bool = False) -> None:
        """Stop data collection."""
        if self._data_acquisition is None:
            self._logger.warning("Mock stop_data_collection")
            return

        self._logger.info("Stopping data collection")
        result = self._data_acquisition.stop_recording()

        if result.success:
            self._mks_on = False
            self._logger.info("Data collection stopped")
            if log_step:
                self.log_step()
        else:
            self._logger.warning(f"Failed to stop data collection: {result.message}")

    def export_to_z_drive(self) -> None:
        """Export experiment files to Z: drive."""
        if not self._experiment_id or not self._experiment_dir:
            self._logger.warning("No experiment ID or directory")
            return

        files_to_copy = list(self._experiment_dir.glob(f"{self._experiment_id}*"))
        if not files_to_copy:
            self._logger.warning(f"No files found matching {self._experiment_id}*")
            return

        target_dir = _load_cloud_root()
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self._logger.error(f"Could not create directory {target_dir}: {exc}")
            return

        copied_count = 0
        for file_path in files_to_copy:
            try:
                shutil.copy2(file_path, target_dir / file_path.name)
                self._logger.info(f"Copied {file_path.name} to {target_dir}")
                copied_count += 1
            except OSError as exc:
                self._logger.error(f"Failed to copy {file_path.name}: {exc}")

        self._logger.info(f"Exported {copied_count} files to {target_dir}")

    # =========================================================================
    # Internal Helpers
    # =========================================================================

    def _ensure_safety_interlocks(self) -> None:
        """Ensure safety interlocks is initialized with all required devices."""
        if self._safety_interlocks is not None or not self.connect_devices:
            return
        try:
            from src.core.config import DeviceConfig
            from src.devices.brooks_mfc import BrooksMFC
            from src.devices.hplc_pump import HPLCPump
            from src.devices.omega_cn7600 import OmegaCN7600

            config = DeviceConfig()
            omega = OmegaCN7600(port=config.omega_port, config=config)
            mfc_devices = [
                BrooksMFC(port=port, config=config) for port in config.mfc_ports
            ]
            hplc_pump = HPLCPump() if config.hplc_port else None
            self._safety_interlocks = SafetyInterlocks(
                temperature_controller=omega,
                mfc_devices=mfc_devices,
                hplc_pump=hplc_pump,
                defaults=self.defaults,
            )
        except Exception as exc:
            self._logger.error(f"Failed to initialize safety interlocks: {exc}")

    def _ensure_temperature_control(self) -> None:
        """Ensure temperature control is initialized."""
        if self._temperature_control is not None or not self.connect_devices:
            return
        try:
            from src.core.config import DeviceConfig
            from src.devices.omega_cn7600 import OmegaCN7600

            self._ensure_safety_interlocks()
            if (
                self._safety_interlocks
                and self._safety_interlocks.temperature_controller
            ):
                controller = self._safety_interlocks.temperature_controller
            else:
                config = DeviceConfig()
                controller = OmegaCN7600(port=config.omega_port, config=config)
            self._temperature_control = TemperatureControl(
                controller=controller, defaults=self.defaults
            )
        except Exception as exc:
            self._logger.error(f"Failed to initialize temperature control: {exc}")

    def _ensure_flow_control(self) -> None:
        """Ensure flow control is initialized."""
        if self._flow_control is not None or not self.connect_devices:
            return
        try:
            from src.core.config import DeviceConfig
            from src.devices.brooks_mfc import BrooksMFC
            from src.devices.hplc_pump import HPLCPump

            self._ensure_safety_interlocks()
            config = DeviceConfig()
            mfc_devices = [
                BrooksMFC(port=port, config=config) for port in config.mfc_ports
            ]
            hplc_pump = HPLCPump() if config.hplc_port else None
            self._flow_control = FlowControl(
                mfc_devices=mfc_devices,
                hplc_pump=hplc_pump,
                safety_interlocks=self._safety_interlocks,
                defaults=self.defaults,
            )
        except Exception as exc:
            self._logger.error(f"Failed to initialize flow control: {exc}")

    def _ensure_data_acquisition(self) -> None:
        """Ensure data acquisition is initialized."""
        if self._data_acquisition is not None:
            return
        try:
            from src.devices.mks_toolweb import MKSToolWeb

            self._data_acquisition = DataAcquisition(
                toolweb=MKSToolWeb(), defaults=self.defaults
            )
        except Exception as exc:
            self._logger.error(f"Failed to initialize data acquisition: {exc}")

    # =========================================================================
    # Properties
    # =========================================================================

    @property
    def experiment_id(self) -> Optional[str]:
        """Get the experiment ID."""
        return self._experiment_id

    @property
    def experiment_dir(self) -> Optional[Path]:
        """Get the experiment directory."""
        return self._experiment_dir
