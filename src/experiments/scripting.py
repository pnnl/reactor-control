"""Experiment scripting interface.

Provides an ExperimentContext for writing flexible experiment scripts
using intuitive atomic operations.

Example:
    from src.experiments.scripting import ExperimentContext, Sample

    with ExperimentContext(name="My Experiment") as exp:
        exp.set_sample(Sample(material_type="catalyst", user_label="Test-001", mass_mg=100.0))
        exp.set_temperature(target=200, rate=5)
        exp.hold(minutes=30, description="Initial stabilization")
        exp.set_gas_flows(total_flow_rate=100, gas_concentrations={"NO_ppm": 500})
        exp.hold(minutes=60, description="Steady-state measurement")
"""

from __future__ import annotations

import logging
import shutil
import time
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from typing import Optional
from dataclasses import asdict

from src.operations.data_acquisition import DataAcquisition
from src.operations.flow_control import FlowControl
from src.operations.sample_management import MaterialParameters
from src.operations.sample_management import SampleManager
from src.operations.step_logger import StepLogger
from src.operations.temperature_control import TemperatureControl


logger = logging.getLogger(__name__)


def _load_data_root() -> Path:
    """Load the data root path from config.

    Returns:
        Path to data root directory.
    """

    import yaml

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

    # Default fallback
    return Path("C:/Data")


@dataclass
class Sample:
    """Sample information for an experiment.

    Args:
        user_label: User-provided sample identifier (required)
        mass_mg: Sample mass in milligrams (required)
        material_type: Type of material (e.g., catalyst, support, standard)
        operator: Name of the operator
        composition: Material composition
        metal: Metal component (e.g., Pd, Cu, Pt)
        support: Support material (e.g., Al2O3, SiO2)
        metal_loading_wt_percent: Metal loading in weight percent
        mesh_size: Mesh size description
        pretreatment_history: Prior treatments
        batch_id: Batch reference
        notes: Free-form notes
    """

    batch_id: str
    mass_mg: float
    operator: str
    composition: str
    metal: str
    support: str
    metal_loading_wt_percent: float
    mesh_size: str
    synthesis_method: str


class ExperimentContext:
    """Context manager for running experiment scripts.

    Provides atomic operations for building flexible experiments.
    Handles setup and cleanup of all hardware operations automatically.

    Attributes:
        name: Experiment name.
        sample: The current sample being tested.
    """

    def __init__(
        self,
        name: str,
        output_dir: Optional[Path] = None,
        connect_devices: bool = False,
        defaults: Optional[dict[str, Any]] = None,
    ) -> None:
        """Initialize the experiment context.

        Args:
            name: Human-readable experiment name.
            output_dir: Directory for experiment output files.
            connect_devices: Whether to connect to physical devices.
            defaults: Optional defaults dictionary.
        """

        self.name = name
        self.output_dir = output_dir
        self.connect_devices = connect_devices
        self.defaults = defaults

        self.sample: Optional[Sample] = None
        self._experiment_id: Optional[str] = None
        self._experiment_dir: Optional[Path] = None
        self._operator: Optional[str] = None
        self._start_time: Optional[datetime] = None
        self._temperature_control: Optional[TemperatureControl] = None
        self._flow_control: Optional[FlowControl] = None
        self._data_acquisition: Optional[DataAcquisition] = None
        self._sample_manager: Optional[SampleManager] = None
        self._step_logger: Optional[StepLogger] = None
        self._is_running: bool = False

        # Track current state for complete step logging
        self._current_temp_target: Optional[float] = None
        self._current_temp_actual: Optional[float] = None
        self._current_ramp_rate: Optional[float] = None
        self._current_hold_minutes: Optional[float] = None
        self._current_gas_flow_sccm: Optional[float] = None
        self._current_gas_concentrations: dict = {}

        # Set up logging
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._setup_logging()

    def _setup_logging(self) -> None:
        """Configure logging for the experiment."""

        # Create experiment ID and directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in self.name)
        self._experiment_id = f"{timestamp}_{safe_name}"

        # Determine output directory (use config if not specified)
        if self.output_dir is None:
            data_root = _load_data_root()
            self.output_dir = data_root
        self._experiment_dir = self.output_dir

        # Create experiment directory
        try:
            self._experiment_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self._logger.warning(f"Could not create experiment dir: {exc}")
            self._experiment_dir = Path(".")

        # Add file handler for experiment log
        log_file = f"{self._experiment_dir / self._experiment_id}.log"
        try:
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(
                logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
            )
            self._logger.addHandler(file_handler)
        except OSError as exc:
            self._logger.warning(f"Could not create log file: {exc}")

    def __enter__(self) -> "ExperimentContext":
        """Enter the experiment context.

        Returns:
            Self.
        """

        self._start_time = datetime.now()
        self._is_running = True

        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        """Exit the experiment context.

        Handles cleanup of all hardware operations.
        """

        self._is_running = False
        self._logger.info(f"=== Experiment Finished: {self.name} ===")

        return False  # Don't suppress exceptions

    # =========================================================================
    # Atomic Operations
    # =========================================================================

    def set_sample(self, sample: Sample) -> None:
        """Set the sample information.

        Creates sample metadata files in the experiment directory.

        Args:
            sample: The sample being tested.
        """

        self.sample = sample
        self._operator = sample.operator

        # Prepare sample metadata
        sample_metadata = asdict(sample)

        # Initialize StepLogger with sample metadata - writes to same file as sample params
        self._step_logger = StepLogger(
            output_dir=self._experiment_dir,
            experiment_id=self._experiment_id,
            operator=sample.operator,
            output_filename=f"{self._experiment_id}.json",
            sample_metadata=sample_metadata,
        )

    def log_step(
        self,
        message: Optional[str] = None,
    ) -> None:
        """Log a progress step.

        Args:
            message: Description of the current step.
        """

        timestamp = datetime.now().strftime("%H:%M:%S")
        if message:
            self._logger.info(f"[{timestamp}] {message}")

        # log to StepLogger
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
            )

    def set_temperature(
        self,
        target: float,
        rate: Optional[float] = None,
        hold_minutes: Optional[float] = None,
    ) -> None:
        """Set the temperature.

        Args:
            target: Target temperature in °C.
            rate: Optional ramp rate in °C/min.
            hold_minutes: Optional hold time in minutes after reaching target.
        """

        # Update current state
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
            return

        rate_str = f" at {rate}°C/min" if rate else ""
        self._logger.info(f"Setting temperature: {target}°C{rate_str}")

        # Build log path for temperature CSV
        log_path = None
        if self._experiment_dir and self._experiment_id:
            log_path = self._experiment_dir / f"{self._experiment_id}.csv"

        result = self._temperature_control.set_temperature(
            target, ramp_rate=rate, log_path=log_path
        )
        if result.success:
            self._logger.info(f"Temperature set successfully")
            # Store actual temperature from result data
            if result.data and "temp_actual" in result.data:
                self._current_temp_actual = result.data["temp_actual"]
        else:
            self._logger.warning(f"Failed to set temperature: {result.message}")

        # Automatically hold if requested
        if hold_minutes is not None:
            self.hold(
                minutes=hold_minutes, description=f"Temp stabilization at {target}°C"
            )

    def hold(self, minutes: float, description: Optional[str] = None) -> None:
        """Hold/pause for a duration.

        Args:
            minutes: Duration to hold in minutes.
            description: Optional description of what is happening during hold.
        """

        desc = description or "hold"
        self._logger.info(f"Holding for {minutes} min: {desc}")
        print(f"[HOLD] {minutes} min - {desc}")

        time.sleep(minutes * 60)

    def set_gas_flows(
        self,
        total_flow_rate: float,
        gas_concentrations: dict[str, float],
    ) -> None:
        """Set gas flows.

        Args:
            total_flow_rate: Total flow rate in SCCM.
            gas_concentrations: Dictionary of gas concentrations.
                - Most gases: ppm (e.g., NO_ppm, NH3_ppm)
                - O2 and H2O: percent (e.g., O2_percent)
        """

        # Update current state
        self._current_gas_flow_sccm = total_flow_rate
        self._current_gas_concentrations = dict(gas_concentrations)

        self._ensure_flow_control()

        if self._flow_control is None:
            self._logger.warning(
                f"Mock set_gas_flows: total={total_flow_rate} SCCM, gases={gas_concentrations}"
            )
            return

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
            # Store actual measured values from result data
            if result.data and "gas_concentrations" in result.data:
                self._current_gas_concentrations = result.data["gas_concentrations"]
        else:
            self._logger.warning(f"Failed to set gas flows: {result.errors}")

    def standby(self, temperature: float = 150.0) -> None:
        """Stop all flows and set temperature to standby.

        Args:
            temperature: Standby temperature in °C (default: 150.0).
        """

        self._ensure_flow_control()

        if self._flow_control is None:
            self._logger.warning("Mock standby")
            return

        if self._flow_control is not None:
            try:
                self._flow_control.set_standby_flow()
            except Exception as exc:
                self._logger.warning(f"Error stopping flows: {exc}")

        if self._temperature_control is not None:
            try:
                self._temperature_control.set_temperature(temperature)
                self._logger.info(
                    f"Temperature control set to ambient ({temperature}C)"
                )
            except Exception as exc:
                self._logger.warning(f"Error stopping temperature control: {exc}")

        # Stop data collection
        if self._data_acquisition is not None:
            try:
                self._data_acquisition.stop_recording()
                self._logger.info("Data collection stopped")
            except Exception as exc:
                self._logger.warning(f"Error stopping data collection: {exc}")

        # Finalize step logger
        if self._step_logger is not None:
            self._step_logger.finalize()
            self._logger.info("Step log finalized")

        # Log final summary
        if self._start_time:
            duration = (datetime.now() - self._start_time).total_seconds()
            self._logger.info(f"Total experiment duration: {duration:.1f} seconds")

    def start_data_collection(self, interval_sec: float = 5.0) -> None:
        """Start data collection.

        Args:
            interval_sec: Data collection interval in seconds (for reference only).
        """

        self._ensure_data_acquisition()

        if self._data_acquisition is None:
            self._logger.warning(
                f"Mock start_data_collection: interval={interval_sec}s"
            )
            return

        self._logger.info(f"Starting data collection: {interval_sec}s interval")

        experiment_name = f"{self._experiment_id}"
        result = self._data_acquisition.start_recording(
            experiment_name=experiment_name,
            data_directory=f"{self._experiment_dir}",
        )

        if result.success:
            self._logger.info("Data collection started")
        else:
            self._logger.warning(f"Failed to start data collection: {result.message}")

    def stop_data_collection(self) -> None:
        """Stop data collection."""

        if self._data_acquisition is None:
            self._logger.warning("Mock stop_data_collection")
            return

        self._logger.info("Stopping data collection")
        result = self._data_acquisition.stop_recording()

        if result.success:
            self._logger.info("Data collection stopped")
        else:
            self._logger.warning(f"Failed to stop data collection: {result.message}")

    def export_to_z_drive(self) -> None:
        """Export experiment files to Z: drive.

        Copies all files starting with self._experiment_id from the experiment
        directory to Z:\ drive.
        """
        if not self._experiment_id:
            self._logger.warning("No experiment ID, cannot export to Z: drive")
            return

        source_dir = self._experiment_dir or self.output_dir
        if not source_dir or not source_dir.exists():
            self._logger.warning(f"Source directory does not exist: {source_dir}")
            return

        # Find all files matching the experiment ID prefix
        files_to_copy = list(source_dir.glob(f"{self._experiment_id}*"))

        if not files_to_copy:
            self._logger.warning(
                f"No files found matching {self._experiment_id}* in {source_dir}"
            )
            return

        # Target directory on Z: drive
        target_dir = Path("Z:/")

        try:
            target_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self._logger.error(f"Could not create Z: drive directory: {exc}")
            return

        # Copy each file
        copied_count = 0
        for file_path in files_to_copy:
            try:
                dest_path = target_dir / file_path.name
                shutil.copy2(file_path, dest_path)
                self._logger.info(f"Copied {file_path.name} to Z:/")
                copied_count += 1
            except OSError as exc:
                self._logger.error(f"Failed to copy {file_path.name}: {exc}")

        self._logger.info(f"Exported {copied_count} files to Z: drive")

    # =========================================================================
    # Internal Helpers
    # =========================================================================

    def _ensure_temperature_control(self) -> None:
        """Ensure temperature control is initialized."""

        if self._temperature_control is not None:
            return

        if not self.connect_devices:
            self._logger.debug("Temperature control not initialized (mock mode)")
            return

        try:
            from src.core.config import DeviceConfig
            from src.devices.omega_cn7600 import OmegaCN7600
            from src.devices.omega_cn7600 import OmegaCN7600

            config = DeviceConfig()  # Uses defaults
            controller = OmegaCN7600(port=config.omega_port, config=config)
            self._temperature_control = TemperatureControl(
                controller=controller,
                defaults=self.defaults,
            )
        except Exception as exc:
            self._logger.error(f"Failed to initialize temperature control: {exc}")

    def _ensure_flow_control(self) -> None:
        """Ensure flow control is initialized."""

        if self._flow_control is not None:
            return

        if not self.connect_devices:
            self._logger.debug("Flow control not initialized (mock mode)")
            return

        try:
            from src.core.config import DeviceConfig
            from src.devices.brooks_mfc import BrooksMFC
            from src.devices.hplc_pump import HPLCPump

            config = DeviceConfig()
            mfc_devices = []

            for port in config.mfc_ports:
                mfc = BrooksMFC(port=port, config=config)
                mfc_devices.append(mfc)

            # Create HPLC pump if configured
            hplc_pump = None
            if config.hplc_port:
                hplc_pump = HPLCPump()
            
            self._flow_control = FlowControl(
                mfc_devices=mfc_devices,
                hplc_pump=hplc_pump,
                defaults=self.defaults,
            )
        except Exception as exc:
            self._logger.error(f"Failed to initialize flow control: {exc}")

    def _ensure_data_acquisition(self) -> None:
        """Ensure data acquisition is initialized."""

        from src.devices.mks_toolweb import MKSToolWeb

        if self._data_acquisition is not None:
            return

        try:
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
