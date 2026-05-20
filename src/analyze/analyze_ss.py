"""Steady-state analysis for isothermal reaction data.

Identifies isothermal ranges and extracts steady-state concentrations.

Example:
    from src.analyze.analyze_ss import load_and_process

    ss_df = load_and_process("experiment_id", data_root)
"""

from __future__ import annotations

import json
import yaml
from dataclasses import dataclass
from pathlib import Path
import sys
import pandas as pd


SRC_PATH = Path(__file__).resolve().parent.parent.parent
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from src.analyze.data_loader import load_experiment_data


def _load_data_root() -> Path:
    """Load the data root path from config."""
    paths_file = Path(__file__).resolve().parent.parent / "config" / "paths.yaml"
    if paths_file.exists():
        with paths_file.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            root = data.get("data_root")
            if root:
                return Path(root)
    return Path("C:/Data")


@dataclass
class IsothermalRange:
    """Container for an isothermal range of data.

    Attributes:
        start_idx: Starting row index in the DataFrame.
        end_idx: Ending row index in the DataFrame.
        start_time: Datetime of the first reading.
        end_time: Datetime of the last reading.
        mean_temp: Mean temperature over the range.
        std_temp: Standard deviation of temperature.
        n_points: Number of data points in the range.
    """

    start_idx: int
    end_idx: int
    start_time: pd.Timestamp
    end_time: pd.Timestamp
    mean_temp: float
    std_temp: float
    n_points: int


@dataclass
class SteadyStateValue:
    """Container for a steady-state data point with error bars.

    Attributes:
        range: The isothermal range this value came from.
        species: Species name (e.g., "no", "no2").
        mean: Mean concentration over the last fraction of the range.
        std: Standard deviation over the last fraction.
        n: Number of points used.
    """

    range: IsothermalRange
    species: str
    mean: float
    std: float
    n: int


def identify_isothermal_ranges(
    ftir_df: pd.DataFrame,
    temp_col: str = "aligned_read_temp",
    time_col: str = "datetime",
    temp_tolerance: float = 1.5,
    min_duration_minutes: float = 15.0,
    end_deviation: float = 2.0,
) -> list[IsothermalRange]:
    """Identify isothermal ranges in temperature data.

    An isothermal range is defined as a period where temperature remains
    within ±temp_tolerance of the initial value. The range ends when
    temperature deviates more than end_deviation from the mean.

    Args:
        ftir_df: DataFrame with temperature and datetime columns.
        temp_col: Name of temperature column.
        time_col: Name of datetime column.
        temp_tolerance: Temperature deviation allowed during range (±°C).
        min_duration_minutes: Minimum duration to qualify as a range (minutes).
        end_deviation: Temperature deviation that ends the range (°C).

    Returns:
        List of IsothermalRange objects.
    """
    ranges = []
    n = len(ftir_df)

    if n == 0:
        return ranges

    temps = ftir_df[temp_col].values
    times = pd.to_datetime(ftir_df[time_col])

    i = 0
    while i < n:
        # Start a new potential range
        initial_temp = temps[i]

        # Move forward until we find a point that deviates too much
        j = i + 1
        while j < n:
            if abs(temps[j] - initial_temp) > temp_tolerance:
                break
            j += 1

        # This potential range goes from i to j-1
        range_temps = temps[i:j]
        mean_temp = float(pd.Series(range_temps).mean())
        std_temp = float(pd.Series(range_temps).std())

        # Check if range duration is sufficient
        duration = times[j - 1] - times[i]
        duration_minutes = duration.total_seconds() / 60

        if duration_minutes >= min_duration_minutes:
            # Now find where the range truly ends (deviation from mean)
            k = i
            while k < j:
                if abs(temps[k] - mean_temp) > end_deviation:
                    break
                k += 1

            ranges.append(
                IsothermalRange(
                    start_idx=i,
                    end_idx=k - 1,
                    start_time=times[i],
                    end_time=times[k - 1],
                    mean_temp=mean_temp,
                    std_temp=std_temp,
                    n_points=k - i,
                )
            )

        i = max(j, i + 1)  # Move forward, avoid infinite loop

    return ranges


def ss_ranges_to_isothermal_ranges(
    ss_ranges: list[dict],
    ftir_df: pd.DataFrame,
    temp_col: str = "aligned_read_temp",
    time_col: str = "datetime",
) -> list[IsothermalRange]:
    """Convert ss_ranges (time boundaries) to IsothermalRange objects.

    Args:
        ss_ranges: List of dicts with "begin_time" and "end_time" as ISO datetime strings.
        ftir_df: DataFrame with temperature and datetime columns.
        temp_col: Name of temperature column.
        time_col: Name of datetime column.

    Returns:
        List of IsothermalRange objects.
    """
    ranges = []
    ftir_times = pd.to_datetime(ftir_df[time_col])
    temps = ftir_df[temp_col].values

    for ss_range in ss_ranges:
        begin_str = ss_range.get("begin_time")
        end_str = ss_range.get("end_time")

        if not begin_str or not end_str:
            continue

        begin_time = pd.to_datetime(begin_str)
        end_time = pd.to_datetime(end_str)

        mask = (ftir_times >= begin_time) & (ftir_times <= end_time)
        indices = ftir_times[mask].index.tolist()

        if len(indices) == 0:
            continue

        start_idx = indices[0]
        end_idx = indices[-1]
        range_temps = temps[start_idx : end_idx + 1]

        mean_temp = float(pd.Series(range_temps).mean())
        std_temp = float(pd.Series(range_temps).std()) if len(range_temps) > 1 else 0.0

        ranges.append(
            IsothermalRange(
                start_idx=start_idx,
                end_idx=end_idx,
                start_time=begin_time,
                end_time=end_time,
                mean_temp=mean_temp,
                std_temp=std_temp,
                n_points=len(indices),
            )
        )

    return ranges


def get_steady_state_data(
    ftir_df: pd.DataFrame,
    ranges: list[IsothermalRange],
    species: list[str] | None = None,
    fraction: float = 0.1,
) -> dict[str, list[SteadyStateValue]]:
    """Extract steady-state values from isothermal ranges.

    For each range, uses the last `fraction` of points to calculate
    mean concentration and standard deviation.

    Args:
        ftir_df: DataFrame with FTIR data.
        ranges: List of isothermal ranges from identify_isothermal_ranges().
        species: List of species to extract. Defaults to ["no", "no2", "n2o", "nh3"].
        fraction: Fraction of range to use for steady-state calculation (default 0.1 = 10%).

    Returns:
        Dict mapping species name to list of SteadyStateValue objects.
    """
    from src.analyze.data_loader import FTIR_COLUMNS

    if species is None:
        species = ["no", "no2", "n2o", "nh3"]

    results = {sp: [] for sp in species}

    for r in ranges:
        # Get the last fraction of points
        n_total = r.end_idx - r.start_idx + 1
        n_use = max(1, int(round(n_total * fraction)))
        start_idx = r.end_idx - n_use + 1
        end_idx = r.end_idx + 1

        subset = ftir_df.iloc[start_idx:end_idx]

        for sp in species:
            if sp not in FTIR_COLUMNS:
                continue

            column = FTIR_COLUMNS[sp]
            values = subset[column]

            results[sp].append(
                SteadyStateValue(
                    range=r,
                    species=sp,
                    mean=float(values.mean()),
                    std=float(values.std()) if len(values) > 1 else 0.0,
                    n=len(values),
                )
            )

    return results


def get_steady_state_df(
    ftir_df: pd.DataFrame,
    ranges: list[IsothermalRange],
    species: list[str] | None = None,
    fraction: float = 0.1,
) -> pd.DataFrame:
    """Get steady-state data as a DataFrame for easy plotting.

    Args:
        ftir_df: DataFrame with FTIR data.
        ranges: List of isothermal ranges.
        species: List of species to extract.
        fraction: Fraction of range to use for calculation.

    Returns:
        DataFrame with columns: temp_mean, temp_std, {species}_mean, {species}_std.
    """
    steady_data = get_steady_state_data(ftir_df, ranges, species, fraction)

    if not species:
        species = list(steady_data.keys())

    rows = []
    n_ranges = len(ranges)

    for i in range(n_ranges):
        r = ranges[i]
        row = {
            "temp_mean": r.mean_temp,
            "temp_std": r.std_temp,
        }

        for sp in species:
            if sp in steady_data and i < len(steady_data[sp]):
                row[f"{sp}_mean"] = steady_data[sp][i].mean
                row[f"{sp}_std"] = steady_data[sp][i].std

        rows.append(row)

    return pd.DataFrame(rows)


def compute_conversions(
    ss_df: pd.DataFrame,
    inlet_no: float = None,
    inlet_nh3: float = None,
    inlet_no2: float = None,
    inlet_n2o: float = None,
) -> pd.DataFrame:
    """Compute NOx/NH3 conversion and N2O/NO2 selectivity.

    Args:
        ss_df: DataFrame with species concentration columns.
        inlet_no: Inlet NO concentration (ppm).
        inlet_nh3: Inlet NH3 concentration (ppm).
        inlet_no2: Inlet NO2 concentration (ppm).
        inlet_n2o: Inlet N2O concentration (ppm).

    Returns:
        DataFrame with added conversion and selectivity columns.
    """
    df = ss_df.copy()

    no_out = df["no_mean"]
    no2_out = df["no2_mean"]
    nh3_out = df["nh3_mean"]
    n2o_out = df["n2o_mean"]

    inlet_nox = inlet_no + inlet_no2
    outlet_nox = no_out + no2_out
    nox_consumed = inlet_nox - outlet_nox

    df["nox_conv"] = nox_consumed / inlet_nox * 100
    if inlet_nh3 > 0:
        df["nh3_conv"] = (inlet_nh3 - nh3_out) / inlet_nh3 * 100
    else:
        df["nh3_conv"] = None
        df["nh3_sel"] = (nh3_out - inlet_nh3) / nox_consumed * 100
    df["n2o_sel"] = 2 * (n2o_out - inlet_n2o) / nox_consumed * 100
    df["no2_sel"] = (no2_out - inlet_no2) / nox_consumed * 100

    df["n2_mean"] = (nox_consumed + (2 * (inlet_n2o - n2o_out)) + (inlet_nh3 - nh3_out)) / 2
    df["n2_sel"] = (2 * df["n2_mean"] / nox_consumed) * 100
    df["mass_balance"] = df["n2o_sel"] + df["nh3_sel"] + df["n2_sel"]

    df.loc[nox_consumed <= 0, ["n2o_sel", "no2_sel", "nh3_sel", "n2_sel", "n2_mean"]] = None
    df.loc[df["no2_sel"] <= 0, ["no2_sel"]] = None
    df.loc[df["nh3_sel"] <= 0, "nh3_sel"] = None
    df.loc[df["n2o_sel"] <= 0, "n2o_sel"] = None
    df.loc[df["n2_sel"] <= 0, "n2_sel"] = None
    df.loc[df["n2_mean"] <= 0, "n2_mean"] = None

    result = df[
        [
            "nox_conv",
            "nh3_conv",
            "n2o_sel",
            "no2_sel",
            "nh3_sel",
            "n2_sel",
            "n2_mean",
            "mass_balance",
        ]
    ].copy()
    return result.round(2)  # type: ignore[return-value]


def load_and_process(
    experiment_id: str,
    ss_ranges: list[dict] | None = None,
    data_root: Path | None = None,
    species: list[str] | None = None,
    fraction: float = 0.1,
    inlet_no: float = 340.0,
    inlet_nh3: float = 0.0,
    inlet_no2: float = 10.0,
    inlet_n2o: float = 0.0,
) -> pd.DataFrame:
    """Load experiment and extract steady-state data.

    Args:
        experiment_id: Experiment identifier (e.g., "20260324_123456_steady-state").
        ss_ranges: Optional list of steady-state time ranges.
            Each dict contains "begin_time" and "end_time" as ISO datetime strings.
            If provided, uses these ranges instead of auto-detection.
        data_root: Root directory where experiment data is stored.
            Defaults to None (loads from config/paths.yaml).
        species: List of species to extract. Defaults to ["no", "no2", "n2o", "nh3"].
        fraction: Fraction of isothermal range to use for steady-state (default 0.1 = 10%).
        inlet_no: Inlet NO concentration in ppm (default 340.0).
        inlet_nh3: Inlet NH3 concentration in ppm (default 0.0).
        inlet_no2: Inlet NO2 concentration in ppm (default 10.0).
        inlet_n2o: Inlet N2O concentration in ppm (default 0.0).
    Returns:
        DataFrame with columns: nox_conv, nh3_conv, n2o_sel, no2_sel.
    """
    if data_root is None:
        data_root = _load_data_root()

    data_path = data_root / experiment_id
    data = load_experiment_data(data_path)

    if data is None:
        raise ValueError(f"Failed to load experiment data for: {experiment_id}")

    if ss_ranges:
        ranges = ss_ranges_to_isothermal_ranges(ss_ranges, data.ftir)
    else:
        ranges = identify_isothermal_ranges(data.ftir)
    ss_df = get_steady_state_df(data.ftir, ranges, species, fraction)
    result_df = compute_conversions(ss_df, inlet_no, inlet_nh3, inlet_no2, inlet_n2o)

    merged_df = pd.concat(
        [ss_df.reset_index(drop=True), result_df.reset_index(drop=True)], axis=1
    )

    output_path = data_root / f"{experiment_id}_processed.csv"
    merged_df.to_csv(output_path, index=False)

    if ss_ranges is not None:
        json_path = data_root / f"{experiment_id}.json"
        if json_path.exists():
            with json_path.open("r", encoding="utf-8") as f:
                existing = json.load(f)
            existing["ss_ranges"] = ss_ranges
            with json_path.open("w", encoding="utf-8") as f:
                json.dump(existing, f, indent=2)

    return merged_df


if __name__ == "__main__":
    ss_df = load_and_process("20260518_150042_steady-state")
