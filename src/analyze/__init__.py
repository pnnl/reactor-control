"""Data analysis module for reactor experiments.

Provides tools for processing and analyzing experimental data.
"""

from __future__ import annotations

from src.analyze.analyze_ss import (
    IsothermalRange,
    SteadyStateValue,
    get_steady_state_data,
    get_steady_state_df,
    identify_isothermal_ranges,
    load_and_process,
)
from src.analyze.data_loader import (
    ExperimentData,
    FTIR_COLUMNS,
    load_experiment_data,
    load_ftir_data,
    load_temperature_data,
    load_experiment_steps,
)

__all__ = [
    # Data loading
    "ExperimentData",
    "FTIR_COLUMNS",
    "load_experiment_data",
    "load_ftir_data",
    "load_temperature_data",
    "load_experiment_steps",
    # Steady-state analysis
    "IsothermalRange",
    "SteadyStateValue",
    "identify_isothermal_ranges",
    "get_steady_state_data",
    "get_steady_state_df",
    "load_and_process",
]
