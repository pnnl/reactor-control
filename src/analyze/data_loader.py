"""Data loader for reactor experiment files.

Loads and parses FTIR spectroscopy data (.prn), temperature logs (.csv),
and experiment step records (.json) from reactor experiments.

Example:
    from src.visualization import load_experiment_data

    # Load all experiment data
    data = load_experiment_data("path/to/experiment_id")

    # Access individual components
    print(data.ftir.head())
    print(data.temperature.head())
    print(data.steps)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# Column names for concentration data in FTIR files
FTIR_COLUMNS = {
    "no": "NO (350,3000) 191C",
    "no2": "NO2 (150) 191C (1of2)",
    "n2o": "N2O (100,200,300) 191C (1of2)",
    "nh3": "NH3 (300) 191C (1of2)",
}


@dataclass
class ExperimentData:
    """Container for aligned experiment data.

    Attributes:
        ftir: DataFrame with FTIR spectroscopy readings and parsed datetime.
        temperature: DataFrame with temperature log readings.
        steps: List of experiment step dictionaries.
        experiment_id: Identifier for the experiment.
        sample_info: Dictionary with sample metadata (if available).
    """

    ftir: pd.DataFrame
    temperature: pd.DataFrame
    steps: list[dict[str, Any]]
    experiment_id: str
    sample_info: dict[str, Any] | None = None


def _parse_ftir_datetime(date_str: str, time_str: str) -> datetime:
    """Parse FTIR datetime from separate date and time strings.

    Args:
        date_str: Date string in format "M/D/YYYY" (e.g., "3/18/2026").
        time_str: Time string from FTIR export.

    Returns:
        Parsed datetime object.
    """
    dt_str = f"{date_str} {time_str}"
    # FTIR exports vary by instrument/setting; support known time variants.
    formats = (
        "%m/%d/%Y %H:%M:%S.%f",  # e.g., 5/18/2026 13:29:05.000
        "%m/%d/%Y %H:%M:%S",  # e.g., 5/18/2026 13:29:05
        "%m/%d/%Y %H:%M.%f",  # e.g., 5/18/2026 13:29.0
    )
    for fmt in formats:
        try:
            return datetime.strptime(dt_str, fmt)
        except ValueError:
            continue
    raise ValueError(
        f"Unsupported FTIR datetime format: '{dt_str}'. Expected one of {formats}"
    )


def _parse_csv_datetime(dt_str: str) -> datetime:
    """Parse datetime from ISO format string.

    Args:
        dt_str: ISO format datetime string (e.g., "2026-03-18T08:48:12.255721").

    Returns:
        Parsed datetime object.
    """
    return datetime.fromisoformat(dt_str)


def load_ftir_data(prn_path: str | Path) -> pd.DataFrame | None:
    """Load FTIR spectroscopy data from .prn file.

    Args:
        prn_path: Path to the .prn file.

    Returns:
        DataFrame with FTIR data including parsed datetime column, or None on error.
    """
    prn_path = Path(prn_path)

    if not prn_path.exists():
        logger.error(f"FTIR file not found: {prn_path}")
        return None

    try:
        df = pd.read_csv(prn_path, sep="\t")

        # Parse datetime from separate Date and Time columns
        df["datetime"] = df.apply(
            lambda row: _parse_ftir_datetime(row["Date"], row["Time"]),
            axis=1,
        )

        logger.info(f"Loaded FTIR data: {len(df)} readings from {prn_path.name}")
        return df

    except Exception as e:
        logger.error(f"Failed to load FTIR file {prn_path}: {e}")
        return None


def load_temperature_data(csv_path: str | Path) -> pd.DataFrame | None:
    """Load temperature log data from .csv file.

    Args:
        csv_path: Path to the temperature .csv file.

    Returns:
        DataFrame with temperature data including parsed datetime column,
        or None on error.
    """
    csv_path = Path(csv_path)

    if not csv_path.exists():
        logger.error(f"Temperature file not found: {csv_path}")
        return None

    try:
        df = pd.read_csv(csv_path)

        # Parse datetime from ISO format string
        df["datetime"] = df["datetime"].apply(_parse_csv_datetime)

        logger.info(f"Loaded temperature data: {len(df)} readings from {csv_path.name}")
        return df

    except Exception as e:
        logger.error(f"Failed to load temperature file {csv_path}: {e}")
        return None


def load_experiment_steps(
    json_path: str | Path,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None, str | None] | None:
    """Load experiment step records from .json file.

    Args:
        json_path: Path to the experiment steps .json file.

    Returns:
        Tuple of (steps_list, sample_info, experiment_id) or None on error.
    """
    json_path = Path(json_path)

    if not json_path.exists():
        logger.error(f"Experiment steps file not found: {json_path}")
        return None

    try:
        with json_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        steps = data.get("steps", [])
        sample_info = data.get("sample")
        experiment_id = data.get("experiment_id")

        logger.info(
            f"Loaded experiment steps: {len(steps)} steps from {json_path.name}"
        )
        return steps, sample_info, experiment_id

    except Exception as e:
        logger.error(f"Failed to load experiment steps file {json_path}: {e}")
        return None


def align_ftir_to_temperature(
    ftir_df: pd.DataFrame,
    temp_df: pd.DataFrame,
    max_time_diff_seconds: float = 10.0,
) -> pd.DataFrame:
    """Align FTIR readings to nearest temperature readings by datetime.

    For each FTIR reading, finds the temperature reading with the closest
    datetime and merges the temperature data.

    Args:
        ftir_df: DataFrame with FTIR data and datetime column.
        temp_df: DataFrame with temperature data and datetime column.
        max_time_diff_seconds: Maximum allowed time difference for alignment.
            Readings with larger differences are excluded.

    Returns:
        DataFrame with FTIR data augmented with nearest temperature values.
    """
    if ftir_df is None or temp_df is None or len(ftir_df) == 0 or len(temp_df) == 0:
        logger.warning("Cannot align: empty DataFrame(s) provided")
        return ftir_df

    aligned_data = []

    ftir_times = ftir_df["datetime"].values
    temp_times = temp_df["datetime"].values
    temp_read_temps = temp_df["read_temp"].values
    temp_target_temps = temp_df["target_temp"].values

    for i, ftir_time in enumerate(ftir_times):
        # Convert to numpy datetime64 for timedelta calculation
        ftir_ts = np.datetime64(ftir_time)

        # Calculate time differences to all temperature readings
        time_diffs = np.abs(temp_times - ftir_ts)

        # Find index of nearest temperature reading
        nearest_idx = np.argmin(time_diffs)
        min_diff_seconds = time_diffs[nearest_idx] / np.timedelta64(1, "s")

        # Only include if within threshold
        if min_diff_seconds <= max_time_diff_seconds:
            row = ftir_df.iloc[i].to_dict()
            row["aligned_read_temp"] = temp_read_temps[nearest_idx]
            row["aligned_target_temp"] = temp_target_temps[nearest_idx]
            row["alignment_time_diff_s"] = min_diff_seconds
            aligned_data.append(row)

    result_df = pd.DataFrame(aligned_data)

    logger.info(
        f"Aligned {len(result_df)} FTIR readings to temperature "
        f"(threshold: {max_time_diff_seconds}s)"
    )

    return result_df


def load_experiment_data(
    base_path: str | Path,
    align_temperatures: bool = True,
    max_time_diff_seconds: float = 10.0,
) -> ExperimentData | None:
    """Load all experiment data files from a base path.

    Expects files with format: {experiment_id}.prn, {experiment_id}.csv,
    {experiment_id}.json

    Args:
        base_path: Base path without extension, or path to any of the data files.
            Can be:
            - Directory containing the data files
            - Path to one of the data files (prn, csv, or json)
            - Base name without extension (e.g., "20260318_084229_steady-state")
        align_temperatures: If True, align FTIR readings to nearest temperature.
        max_time_diff_seconds: Maximum time difference for temperature alignment.

    Returns:
        ExperimentData container with loaded and optionally aligned data,
        or None on error.
    """
    base_path = Path(base_path)

    # If a file path is provided, extract the base directory and experiment ID
    if base_path.suffix in {".prn", ".csv", ".json"}:
        experiment_id = base_path.stem
        base_path = base_path.parent
    elif base_path.is_dir():
        # Assume experiment_id is in the directory name or we need to find it
        experiment_id = base_path.name
    else:
        # Base path without extension - extract directory and experiment_id
        experiment_id = base_path.name
        base_path = base_path.parent

    prn_path = base_path / f"{experiment_id}.prn"
    csv_path = base_path / f"{experiment_id}.csv"
    json_path = base_path / f"{experiment_id}.json"

    # Load all data files
    ftir_df = load_ftir_data(prn_path)
    temp_df = load_temperature_data(csv_path)

    steps_result = load_experiment_steps(json_path)
    if steps_result is None:
        steps = []
        sample_info = None
        loaded_experiment_id = experiment_id
    else:
        steps, sample_info, loaded_experiment_id = steps_result
        # Use experiment_id from file if available
        if loaded_experiment_id:
            experiment_id = loaded_experiment_id

    if ftir_df is None:
        logger.error("Failed to load required FTIR data")
        return None

    # Align temperatures if requested
    if align_temperatures and temp_df is not None:
        ftir_df = align_ftir_to_temperature(ftir_df, temp_df, max_time_diff_seconds)

    return ExperimentData(
        ftir=ftir_df,
        temperature=temp_df,
        steps=steps,
        experiment_id=experiment_id,
        sample_info=sample_info,
    )


if __name__ == "__main__":
    # Example usage
    data_ir = load_ftir_data(
        r"C:\Users\labuser\reactor_control\src\visualization\20260318_084229_steady-state.prn"
    )
    data_temp = load_temperature_data(
        r"C:\Users\labuser\reactor_control\src\visualization\20260318_084229_steady-state.csv"
    )
    data_all = load_experiment_data(
        r"C:\Users\labuser\reactor_control\src\visualization\20260318_084229_steady-state"
    )
    print(data_ir.head())
