"""Data acquisition operations for MKS ToolWEB."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
from typing import Optional
from typing import TYPE_CHECKING
import logging
import sys

SRC_PATH = Path(__file__).resolve().parent.parent.parent
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from src.devices.mks_toolweb import MKSToolWeb
from src.operations.base import BaseOperation, OperationResult


if TYPE_CHECKING:
    from .step_logger import StepLogger


logger = logging.getLogger(__name__)


class DataAcquisition(BaseOperation):
    """Operations for MKS ToolWEB data acquisition."""

    def __init__(
        self,
        toolweb: MKSToolWeb,
        defaults: Optional[dict[str, Any]] = None,
        paths: Optional[dict[str, Any]] = None,
        step_logger: Optional[StepLogger] = None,
    ) -> None:
        super().__init__(
            name="DataAcquisition",
            defaults=defaults,
            paths=paths,
            step_logger=step_logger,
        )
        self.toolweb = toolweb

    def start_recording(
        self,
        experiment_name: Optional[str] = None,
        data_directory: Optional[Path] = None,
        auto_export: Optional[bool] = None,
    ) -> OperationResult:
        """Start data acquisition with ToolWEB.

        Args:
            experiment_name: Optional experiment name override.
            data_directory: Optional data directory override.
            auto_export: Optional auto-export override.

        Returns:
            OperationResult indicating success.
        """

        data_defaults = self.defaults.get("data_acquisition", {})
        if not isinstance(data_defaults, dict):
            data_defaults = {}

        if auto_export is None:
            auto_export = bool(data_defaults.get("auto_export", True))

        if data_directory is None:
            data_dir_value = data_defaults.get("data_directory")
            if isinstance(data_dir_value, str) and data_dir_value.strip():
                data_directory = Path(data_dir_value)
            else:
                data_directory = self.get_data_root()

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if experiment_name is None:
            experiment_name = f"{timestamp}_experiment"

        mks_data_dir = data_directory
        mks_data_dir.mkdir(parents=True, exist_ok=True)

        if not self.toolweb.is_connected:
            if not self.toolweb.connect():
                return OperationResult(
                    success=False,
                    message="Failed to connect to ToolWEB.",
                )

        prn_path = mks_data_dir / f"{experiment_name}.prn"
        if not self.toolweb.set_prn_path(str(prn_path)):
            return OperationResult(
                success=False,
                message="Failed to set PRN path.",
            )

        if not self.toolweb.start_run():
            return OperationResult(
                success=False,
                message="Failed to start ToolWEB run.",
            )

        message = "ToolWEB recording started."
        if not auto_export:
            message = "ToolWEB recording started (auto export disabled)."

        return OperationResult(
            success=True,
            message=message,
            data={
                "experiment_name": experiment_name,
                "data_directory": str(mks_data_dir),
            },
        )

    def stop_recording(self, auto_export: Optional[bool] = None) -> OperationResult:
        """Stop data acquisition.

        Args:
            auto_export: Optional auto-export override.

        Returns:
            OperationResult indicating success.
        """

        data_defaults = self.defaults.get("data_acquisition", {})
        if not isinstance(data_defaults, dict):
            data_defaults = {}

        if auto_export is None:
            auto_export = bool(data_defaults.get("auto_export", True))

        if not self.toolweb.stop_run():
            return OperationResult(
                success=False,
                message="Failed to stop ToolWEB run.",
            )

        if not auto_export:
            return OperationResult(
                success=True,
                message="ToolWEB recording stopped (auto export disabled).",
            )

        return OperationResult(
            success=True,
            message="ToolWEB recording stopped.",
        )


if __name__ == "__main__":
    toolweb = MKSToolWeb()
    data_acquisition = DataAcquisition(toolweb=toolweb)

    result = data_acquisition.start_recording(
        experiment_name="20260303_nn2157-147_pdal2o3",
        data_directory=Path("C:\\Data\\nelson\\2026"),
        auto_export=True,
    )

    # result = data_acquisition.stop_recording(auto_export=True)
    print(result)

    """
    - Writing to .ini does not seem to configure the software. Only works when done manually. 
    - overwrite vs. append
    """
