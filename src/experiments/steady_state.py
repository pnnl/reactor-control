"""Steady-State Experiment.

Run this script to execute a steady-state experiment:
    python -m src.experiments.steady_state

Or from project root:
    python src/experiments/steady_state.py

Copy and modify this file for your own experiments.
"""

from __future__ import annotations

import sys
import pandas as pd
from pathlib import Path
from typing import Optional

SRC_PATH = Path(__file__).resolve().parent.parent.parent
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))


from src.experiments import Experiment, Sample
from src.analyze import load_and_process


def sample_info(
    batch_id: str,
    mass_mg: float,
    operator: str,
    composition: str,
    metal: str,
    support: str,
    metal_loading_wt_percent: float,
    mesh_size: str,
    synthesis_method: str,
    name: str = "steady-state",
    connect_devices: bool = True,
    sample: Optional[Sample] = None,
) -> Experiment:
    """Define sample information.

    Args:
        name: Experiment name used in output files.
        connect_devices: If True, connect to real hardware. If False, mock mode.
        sample: Sample information. If None, uses default sample.

    Returns:
        Experiment instance with sample set.
    """

    exp = Experiment(
        name=name,
        output_dir=None,
        connect_devices=connect_devices,
    )

    if sample is None:
        sample = Sample(
            batch_id=batch_id,
            mass_mg=mass_mg,
            operator=operator,
            composition=composition,
            metal=metal,
            support=support,
            metal_loading_wt_percent=metal_loading_wt_percent,
            mesh_size=mesh_size,
            synthesis_method=synthesis_method,
        )
    exp.set_sample(sample)

    return exp

def pretreatment(
    exp: Experiment,
    target_temps: list[float],
    ramp_rates: list[float],
    hold_times: list[float],
    gas_flows: list[dict],
) -> Experiment:
    """Run pretreatment steps before the main experiment.

    Args:
        exp: Experiment instance to perform pretreatment on.
        target_temps: List of temperature targets, one per step.
        ramp_rates: List of ramp rates in °C/min. Shorter lists extend to match.
        hold_times: List of hold times in minutes. Shorter lists extend to match.
        gas_flows: List of gas flow dicts. Shorter lists extend to match.
            Each dict should have 'total_flow_rate' and 'gas_concentrations'.

    Returns:
        Experiment instance after pretreatment.
    """
    max_len = len(target_temps)
    ramp_rates = (ramp_rates * max_len)[:max_len]
    hold_times = (hold_times * max_len)[:max_len]
    gas_flows = (gas_flows * max_len)[:max_len]

    for temps, ramps, holds, gas in zip(
        target_temps, ramp_rates, hold_times, gas_flows
    ):
        exp.set_gas_flows(
            total_flow_rate=gas["total_flow_rate"],
            gas_concentrations=gas["gas_concentrations"],
        )

        exp.run_temperature_program(
            target_temps=[temps],
            ramp_rates=[ramps],
            hold_times=[holds],
        )

    return exp

def run_steady_state(
    exp: Experiment,
    gas_flow: dict,
    target_temps: list[float],
    ramp_rates: list[float],
    hold_times: list[float],
) -> Experiment:
    """Run a steady-state experiment.

    Args:
        target_temps: Temperature program targets (required).
        ramp_rates: Temperature ramp rates in °C/min (required). Must match len of target_temps.
        hold_times: Temperature hold times in minutes (required). Must match len of target_temps.
        gas_flow: Gas flow configuration. Dict should have 'total_flow_rate' and 'gas_concentrations' keys.

    Returns:
        Experiment instance.
    """

    exp.set_gas_flows(
        total_flow_rate=gas_flow["total_flow_rate"],
        gas_concentrations=gas_flow["gas_concentrations"],
    )

    exp.start_data_collection()

    exp.run_temperature_program(
        target_temps=target_temps,
        ramp_rates=ramp_rates,
        hold_times=hold_times,
    )

    exp.stop_data_collection()

    load_and_process(exp.experiment_id, ss_ranges=exp.ss_ranges)
    exp.export_to_z_drive()

    return exp

def standby(
        exp: Experiment,
        standby_temp: float = 120
) -> None:
    """Set system to standby mode after experiment."""

    exp.standby(temperature=standby_temp)
    exp.close()


if __name__ == "__main__":

    def experiment_1(standby: bool = True) -> None:
        exp = sample_info(
            batch_id="nn2061",
            mass_mg=50.0,
            operator="nelson",
            composition="Pd/Al2O3",
            metal="Pd",
            support="g-Al2O3",
            metal_loading_wt_percent=0.1,
            mesh_size="30-60",
            synthesis_method="",
        )

        exp = pretreatment(
            exp=exp,
            target_temps=[650, 400],
            ramp_rates=[10.0],
            hold_times=[4*60, 30],
            gas_flows=[
                {
                    "total_flow_rate": None,
                    "gas_concentrations": {
                        "h2": 9300.0,
                        "nh3": 0.0,
                        "no": 0.0,
                        "o2": 0.0,
                        "h2o": 0.0,
                        "n2": 0.0,
                    },
                },
                              {
                    "total_flow_rate": 410,
                    "gas_concentrations": {
                        "h2": 9300.0,
                        "nh3": 0.0,
                        "no": 350.0,
                        "o2": 0.0,
                        "h2o": 20.0,
                    },
                },
            ],
        )

        exp = run_steady_state(
            exp=exp,
            target_temps=[120, 140, 160, 180, 200, 225, 250, 275, 300, 350, 400],
            ramp_rates=[10.0],
            hold_times=[30.0],
            gas_flow={
                "total_flow_rate": 410,
                "gas_concentrations": {
                    "h2": 9300.0,
                    "nh3": 0.0,
                    "no": 350.0,
                    "o2": 0.0,
                    "h2o": 20.0,
                },
            },
        )

        exp.standby() if standby else exp.close()

    def experiment_2(standby: bool = True) -> None:
        exp = sample_info(
            batch_id="nn2061",
            mass_mg=50.0,
            operator="nelson",
            composition="Pd/Al2O3",
            metal="Pd",
            support="g-Al2O3",
            metal_loading_wt_percent=0.1,
            mesh_size="30-60",
            synthesis_method="",
        )

        exp = pretreatment(
            exp=exp,
            target_temps=[400],
            ramp_rates=[10.0],
            hold_times=[30.0],
            gas_flows=[
                {
                    "total_flow_rate": 410,
                    "gas_concentrations": {
                        "h2": 9300.0,
                        "nh3": 0.0,
                        "no": 350.0,
                        "o2": 1.0,
                        "h2o": 20.0,
                    },
                },
            ],
        )

        exp = run_steady_state(
            exp=exp,
            target_temps=[120, 140, 160, 180, 200, 225, 250, 275, 300, 350, 400],
            ramp_rates=[10.0],
            hold_times=[30.0],
            gas_flow={
                "total_flow_rate": 410,
                "gas_concentrations": {
                    "h2": 9300.0,
                    "nh3": 0.0,
                    "no": 350.0,
                    "o2": 1.0,
                    "h2o": 20.0,
                },
            },
        )

        exp.standby() if standby else exp.close()

    def test(standby: bool = True) -> None:
        exp = sample_info(
            batch_id="nn2061",
            mass_mg=50.0,
            operator="nelson",
            composition="Pd/Al2O3",
            metal="Pd",
            support="g-Al2O3",
            metal_loading_wt_percent=0.1,
            mesh_size="30-60",
            synthesis_method="",
        )

        exp = pretreatment(
            exp=exp,
            target_temps=[250, 260],
            ramp_rates=[10],
            hold_times=[1*0.5, 0.5],
            gas_flows=[
                {
                    "total_flow_rate": None,
                    "gas_concentrations": {
                        "h2": 9300.0,
                        "nh3": 0.0,
                        "no": 0.0,
                        "o2": 0.0,
                        "h2o": 0.0,
                        "n2": 0.0,
                    },
                },
                {
                    "total_flow_rate": 410,
                    "gas_concentrations": {
                        "h2": 9300.0,
                        "nh3": 0.0,
                        "no": 350.0,
                        "o2": 1.0,
                        "h2o": 20.0,
                    },
                },
            ],
        )

        exp = run_steady_state(
            exp=exp,
            target_temps=[250],
            ramp_rates=[0.0],
            hold_times=[1.0],
            gas_flow={
                "total_flow_rate": 410,
                "gas_concentrations": {
                    "h2": 9300.0,
                    "nh3": 0.0,
                    "no": 350.0,
                    "o2": 1.0,
                    "h2o": 20.0,
                },
            },
        )

        exp.standby() if standby else exp.close()

    experiment_1(standby=False)
    experiment_2()
    # test(standby=False)


"""
Open Items:
1. if sample info exists, don't write.
2. introduce hold argument in run_steady_state()?
"""
