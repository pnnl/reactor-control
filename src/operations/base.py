"""Base classes and utilities for operations layer."""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Any
from typing import Optional
from typing import TYPE_CHECKING
import logging
import sys

import yaml


SRC_PATH = Path(__file__).resolve().parent.parent.parent
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))


if TYPE_CHECKING:
    from .step_logger import StepLogger


logger = logging.getLogger(__name__)


@dataclass
class OperationResult:
    """Structured outcome for an operation.

    Args:
        success: Whether the operation succeeded.
        message: Human-readable summary message.
        data: Optional data payload.
        errors: List of error messages.
        warnings: List of warning messages.
    """

    success: bool
    message: str
    data: Optional[dict[str, Any]] = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        """Convert the result to a dictionary.

        Returns:
            Dictionary representation of the result.
        """

        return {
            "success": self.success,
            "message": self.message,
            "data": self.data,
            "errors": self.errors,
            "warnings": self.warnings,
        }


class OperationError(RuntimeError):
    """Base exception type for operation failures."""


class OperationTimeoutError(OperationError):
    """Raised when an operation exceeds a timeout."""


class SafetyViolationError(OperationError):
    """Raised when safety interlocks fail."""


class BaseOperation:
    """Base class for all operations modules.

    Args:
        name: Human-readable operation name.
        defaults: Optional defaults dictionary override.
        paths: Optional paths dictionary override.
        step_logger: Optional step logger for operation tracking.
    """

    def __init__(
        self,
        name: str,
        defaults: Optional[dict[str, Any]] = None,
        paths: Optional[dict[str, Any]] = None,
        step_logger: Optional[StepLogger] = None,
    ) -> None:
        self.name = name
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.defaults = defaults or self._load_defaults()
        self.paths = paths or self._load_paths()
        self.step_logger = step_logger

    def _load_defaults(self) -> dict[str, Any]:
        """Load defaults.yaml configuration.

        Returns:
            Defaults dictionary (empty if unavailable).
        """

        defaults_path = Path(__file__).parent.parent.parent / "config" / "defaults.yaml"
        return self._load_yaml(defaults_path)

    def _load_paths(self) -> dict[str, Any]:
        """Load paths.yaml configuration.

        Returns:
            Paths dictionary (empty if unavailable).
        """

        paths_path = Path(__file__).parent.parent.parent / "config" / "paths.yaml"
        return self._load_yaml(paths_path)

    def _load_yaml(self, path: Path) -> dict[str, Any]:
        """Load a YAML file safely.

        Args:
            path: Path to the YAML file.

        Returns:
            Parsed YAML as dictionary or empty dict on error.
        """

        if not path.exists():
            self.logger.warning(f"Config file not found: {path}")
            return {}
        try:
            with path.open("r", encoding="utf-8") as handle:
                data = yaml.safe_load(handle) or {}
            if not isinstance(data, dict):
                self.logger.error(f"Invalid YAML structure in {path}")
                return {}
            return data
        except (OSError, yaml.YAMLError) as exc:
            self.logger.error(f"Failed to load YAML {path}: {exc}")
            return {}

    def get_data_root(self) -> Path:
        """Resolve the data root directory.

        Returns:
            Path to the data root directory.
        """

        data_root = self.paths.get("data_root")
        if isinstance(data_root, str) and data_root.strip():
            return Path(data_root)
        return Path("data")

    def resolve_experiment_dir(self, experiment_id: str) -> Path:
        """Resolve the experiment directory for an experiment ID.

        Args:
            experiment_id: Experiment identifier.

        Returns:
            Path to the experiment directory.
        """

        return self.get_data_root() / experiment_id

    def log_step(self, **kwargs: Any) -> None:
        """Log a step via the step logger if available.

        Args:
            **kwargs: Step parameters forwarded to StepLogger.log_step.
        """

        if self.step_logger is None:
            return
        self.step_logger.log_step(**kwargs)
