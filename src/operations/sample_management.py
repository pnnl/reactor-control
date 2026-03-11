"""Sample management operations."""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import asdict
from dataclasses import field
from datetime import datetime
from pathlib import Path
from typing import Any
from typing import Optional
from typing import TYPE_CHECKING
import json
import logging
import re
import sys

SRC_PATH = Path(__file__).resolve().parent.parent.parent
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from src.operations.base import BaseOperation
from src.operations.base import OperationResult


if TYPE_CHECKING:
    from .step_logger import StepLogger


logger = logging.getLogger(__name__)


@dataclass
class MaterialParameters:
    """Material parameters for sample metadata.

    Args:
        user_label: User-provided sample identifier.
        material_type: Material type (e.g., catalyst, support, standard).
        mass_mg: Sample mass in milligrams.
        operator: Operator name.
        composition: Material composition.
        mesh_size: Mesh size description.
        pretreatment_history: Prior treatments.
        batch_id: Batch reference.
        notes: Free-form notes.
        metal: Metal component (e.g., Pd, Cu, Pt).
        support: Support material (e.g., Al2O3, SiO2).
        metal_loading_wt_percent: Metal loading in weight percent.
    """

    user_label: str
    material_type: str
    mass_mg: float
    operator: Optional[str] = None
    composition: Optional[str] = None
    mesh_size: Optional[str] = None
    pretreatment_history: Optional[str] = None
    batch_id: Optional[str] = None
    notes: Optional[str] = None
    metal: Optional[str] = None
    support: Optional[str] = None
    metal_loading_wt_percent: Optional[float] = None
    validation_errors: list[str] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        if not self.user_label or not self.user_label.strip():
            self.validation_errors.append("user_label is required")
        if not self.material_type or not self.material_type.strip():
            self.validation_errors.append("material_type is required")
        if self.mass_mg <= 0:
            self.validation_errors.append("mass_mg must be positive")


class SampleManager(BaseOperation):
    """Operations for sample ID generation and metadata output."""

    def __init__(
        self,
        defaults: Optional[dict[str, Any]] = None,
        paths: Optional[dict[str, Any]] = None,
        step_logger: Optional[StepLogger] = None,
    ) -> None:
        super().__init__(
            name="SampleManager",
            defaults=defaults,
            paths=paths,
            step_logger=step_logger,
        )

    def create_sample(
        self,
        parameters: MaterialParameters,
        experiment_root: Optional[Path] = None,
        experiment_id: Optional[str] = None,
    ) -> OperationResult:
        """Create a sample entry with metadata files.

        Args:
            parameters: Material parameters for the sample.
            experiment_root: Optional root directory override.
            experiment_id: Optional experiment ID to use (instead of generating one).

        Returns:
            OperationResult with generated IDs and paths.
        """

        if parameters.validation_errors:
            return OperationResult(
                success=False,
                message="Invalid sample parameters.",
                errors=parameters.validation_errors,
            )

        # Use provided experiment_id or generate one
        if experiment_id is None:
            sample_id = self._generate_sample_id(parameters)
            if sample_id is None:
                return OperationResult(
                    success=False,
                    message="Invalid sample parameters.",
                    errors=["Invalid material_type or user_label."],
                )
            experiment_id = sample_id

        experiment_root = experiment_root or self.get_data_root()
        experiment_dir = experiment_root / experiment_id

        try:
            experiment_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return OperationResult(
                success=False,
                message="Failed to create experiment directory.",
                errors=[str(exc)],
            )

        # Use experiment_id as base name with _expParams.json suffix
        metadata_path = experiment_root / f"{experiment_id}_expParams.json"
        metadata = asdict(parameters)
        metadata["sample_id"] = parameters.user_label
        metadata["experiment_id"] = experiment_id

        try:
            with metadata_path.open("w", encoding="utf-8") as handle:
                json.dump(metadata, handle, indent=2)
        except OSError as exc:
            return OperationResult(
                success=False,
                message="Failed to write sample metadata.",
                errors=[str(exc)],
            )

        self.log_step(step_type="sample", status="completed")

        return OperationResult(
            success=True,
            message="Sample created.",
            data={
                "sample_id": parameters.user_label,
                "experiment_id": experiment_id,
                "experiment_dir": str(experiment_dir),
            },
        )

    def _generate_sample_id(self, parameters: MaterialParameters) -> Optional[str]:
        """Generate a sample ID.

        Args:
            parameters: Material parameters.

        Returns:
            Sample ID string.
        """

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        material_type = self._sanitize(parameters.material_type)
        user_label = self._sanitize(parameters.user_label)
        # if not material_type or not user_label:
        #     return None
        return f"{timestamp}_{material_type}_{user_label}"

    def _sanitize(self, value: str) -> str:
        """Sanitize a string for safe filenames."""

        cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", value.strip())
        return cleaned.strip("_")


if __name__ == "__main__":
    from pathlib import Path

    manager = SampleManager()

    params = MaterialParameters(
        user_label="Cu-SCR-001",
        material_type="catalyst",
        mass_mg=150.0,
        operator="labuser",
        composition="Cu-ZSM5",
        mesh_size="40-60",
        pretreatment_history="Calcined at 500C",
        batch_id="BATCH-2026-001",
        notes="SCR catalyst for NOx reduction testing",
    )

    result = manager.create_sample(
        parameters=params,
        experiment_root=Path("C:\\Data\\nelson\\test"),
    )

    print(f"Success: {result.success}")
    print(f"Message: {result.message}")
    if result.data:
        print(f"Sample ID: {result.data.get('sample_id')}")
        print(f"Experiment Dir: {result.data.get('experiment_dir')}")
