"""Data reprocessing module for batch analysis of experiment files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import pandas as pd
import yaml


SRC_PATH = Path(__file__).resolve().parent.parent.parent
if str(SRC_PATH) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(SRC_PATH))

from src.analyze.analyze_ss import compute_conversions


class DataWriter:
    """Batch processor for experiment data files."""

    def __init__(self, data_root: Optional[Path] = None) -> None:
        """Initialize the data writer.

        Args:
            data_root: Root directory containing experiment data.
                Defaults to C:/Data via config.
        """
        self.data_root = data_root or self._load_data_root()

    def _load_data_root(self) -> Path:
        """Load data root path from config."""
        paths_file = Path(__file__).resolve().parent.parent / "config" / "paths.yaml"
        if paths_file.exists():
            with paths_file.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                root = data.get("data_root")
                if root:
                    return Path(root)
        return Path("C:/Data")

    def _find_json_files(self, operator: Optional[str] = None) -> list[Path]:
        """Find .json files in data root.

        Args:
            operator: If provided, only return files matching this operator.

        Returns:
            List of matching .json file paths.
        """
        json_files = list(self.data_root.glob("*.json"))
        if operator is None:
            return json_files

        matching = []
        for json_path in json_files:
            try:
                with json_path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data.get("operator") == operator:
                        matching.append(json_path)
            except (json.JSONDecodeError, OSError):
                continue
        return matching

    def _get_experiment_id(self, json_path: Path) -> str:
        """Extract experiment ID from JSON file path."""
        return json_path.stem

    def _get_processed_csv(self, experiment_id: str) -> Optional[Path]:
        """Get path to processed CSV if it exists."""
        csv_path = self.data_root / f"{experiment_id}_processed.csv"
        return csv_path if csv_path.exists() else None

    def _has_column(self, csv_path: Path, column: str) -> bool:
        """Check if CSV has a specific column."""
        try:
            df = pd.read_csv(csv_path, nrows=1)
            return column in df.columns
        except (pd.errors.EmptyDataError, OSError):
            return False


    def reprocess_all(
        self,
        operator: Optional[str] = None,
        column: str = "nox_conv",
        dry_run: bool = False,
        **load_and_process_kwargs,
    ) -> dict[str, bool]:
        """Reprocess all experiments matching criteria.

        Args:
            operator: Filter by operator name (e.g., "nelson").
                None means process all.
            column: Column to check for (default: "nox_conv").
            dry_run: If True, only print what would be processed.
            **load_and_process_kwargs: Arguments passed to load_and_process().

        Returns:
            Dict mapping experiment_id to reprocessing success.
        """
        json_files = self._find_json_files(operator=operator)
        results = {}

        for json_path in json_files:
            experiment_id = self._get_experiment_id(json_path)
            csv_path = self._get_processed_csv(experiment_id)

            if csv_path is None:
                print(f"  {experiment_id}: No processed CSV, skipping")
                results[experiment_id] = False
                continue

            if self._has_column(csv_path, column):
                print(f"  {experiment_id}: Has '{column}', skipping")
                results[experiment_id] = False
                continue

            if dry_run:
                print(f"  {experiment_id}: Would reprocess (missing '{column}')")
                results[experiment_id] = None
            else:
                print(f"  {experiment_id}: Reprocessing...")
                try:
                    ss_df = pd.read_csv(csv_path)
                    result_df = compute_conversions(
                        ss_df,
                        **load_and_process_kwargs,
                    )
                    merged_df = pd.concat(
                        [ss_df.reset_index(drop=True), result_df.reset_index(drop=True)], axis=1
                    )
                    data_root = self._load_data_root()
                    output_path = data_root / f"{experiment_id}_processed.csv"
                    merged_df.to_csv(output_path, index=False)

                    results[experiment_id] = True
                except Exception as e:
                    results[experiment_id] = False
                    print(f"    Error: {e}")

        return results


if __name__ == "__main__":
    writer = DataWriter()

    writer.reprocess_all(
        operator="nelson",
        column="nox_conv",
        inlet_no=340.0,
        inlet_nh3=0.0,
        inlet_no2=10.0,
        inlet_n2o=0.0,
    )
