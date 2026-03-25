"""Plotting utilities for reactor experiment data.

Provides functions for visualizing FTIR concentration data aligned with temperature.

Example:
    import matplotlib.pyplot as plt
    from src.visualization import load_experiment_data
    from src.visualization.plot_ss import plot_concentrations_vs_temperature

    data = load_experiment_data("path/to/experiment_id")
    fig = plot_concentrations_vs_temperature(data.ftir)
    plt.show()
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from src.analyze.data_loader import FTIR_COLUMNS
from src.analyze.analyze_ss import (get_steady_state_df, identify_isothermal_ranges)


def plot_steady_state(
    ftir_df: pd.DataFrame,
    species: list[str] | None = None,
    temp_col: str = "temp_mean",
    output_path: str | Path | None = None,
    figsize: tuple[float, float] = (12, 8),
    temp_tolerance: float = 1.5,
    min_duration_minutes: float = 15.0,
    end_deviation: float = 2.0,
    steady_fraction: float = 0.1,
) -> tuple:
    """Plot steady-state concentrations with error bars.

    Identifies isothermal stretches, extracts steady-state values (last 10%),
    and plots with error bars.

    Args:
        ftir_df: DataFrame with FTIR data and temperature column.
        species: List of species to plot. Defaults to all four.
        temp_col: Name of temperature column.
        output_path: Optional path to save the figure.
        figsize: Figure size as (width, height).
        temp_tolerance: Temperature deviation allowed during isothermal stretch (±°C).
        min_duration_minutes: Minimum duration for isothermal stretch (minutes).
        end_deviation: Temperature deviation that ends the stretch (°C).
        steady_fraction: Fraction of stretch to use for steady-state (default 0.1 = 10%).

    Returns:
        Tuple of (matplotlib Figure, DataFrame with steady-state data).
    """

    if species is None:
        species = ["no", "no2", "n2o", "nh3"]

    # Identify isothermal ranges
    ranges = identify_isothermal_ranges(
        ftir_df,
        temp_col=temp_col,
        temp_tolerance=temp_tolerance,
        min_duration_minutes=min_duration_minutes,
        end_deviation=end_deviation,
    )

    if not ranges:
        raise ValueError("No isothermal ranges found in data")

    # Get steady-state values
    ss_df = get_steady_state_df(ftir_df, ranges, species, steady_fraction)

    # Create plots
    n = len(species)
    cols = 2 if n > 1 else 1
    rows = (n + 1) // 2

    fig, axes = plt.subplots(rows, cols, figsize=figsize)
    fig.suptitle("Steady-State Concentrations", fontsize=14, fontweight="bold")

    if n == 1:
        axes = [axes]
    else:
        axes = axes.flatten()

    for i, sp in enumerate(species):
        ax = axes[i]
        ax.errorbar(
            ss_df["temp_mean"],
            ss_df[f"{sp}_mean"],
            yerr=ss_df[f"{sp}_std"],
            fmt="o",
            capsize=4,
            markersize=8,
        )
        ax.set_xlabel("Temperature (°C)")
        ax.set_ylabel(f"{sp.upper()} Concentration (ppm)")
        ax.set_title(f"{sp.upper()} (n={len(ranges)} points)")
        ax.grid(True, alpha=0.3)

    # Hide unused axes
    for i in range(n, len(axes)):
        axes[i].set_visible(False)

    plt.tight_layout()

    if output_path:
        plt.savefig(output_path, dpi=300, bbox_inches="tight")

    return fig, ss_df

