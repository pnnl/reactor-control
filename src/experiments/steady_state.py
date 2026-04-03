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
        name: str = "steady-state",
        connect_devices: bool = True,
        sample: Optional[Sample] = None
        ) -> Sample:
    """Define sample information.
    
    Args:
        name: Experiment name used in output files.
        connect_devices: If True, connect to real hardware. If False, mock mode.
        sample: Sample information. If None, uses default sample.
        
    Returns:
        Sample instance with defined information.
    """

    exp = Experiment(
        name=name,
        output_dir=None,
        connect_devices=connect_devices,
    )

    if sample is None:
        sample = Sample(
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
    exp.set_sample(sample)

    return exp

def pretreatment(
        exp: Experiment,
        gas_flow: dict,
        target_temps: list[float],
        ramp_rates: list[float],
        hold_times: list[float],
) -> Experiment:
    """Run pretreatment steps before the main experiment.
    
    Args:
        exp: Experiment instance to perform pretreatment on.
        target_temps: Temperature program targets (required).
        ramp_rates: Temperature ramp rates in °C/min (required). Must match len of target_temps.
        hold_times: Temperature hold times in minutes (required). Must match len of target_temps.
        gas_flow: Gas flow configuration. Dict should have 'total_flow_rate' and 'gas_concentrations' keys.
        
    Returns:
        Experiment instance after pretreatment.
    """
    exp.set_gas_flows(
        total_flow_rate=gas_flow["total_flow_rate"],
        gas_concentrations=gas_flow["gas_concentrations"],
    )

    exp.run_temperature_program(
        target_temps=target_temps,
        ramp_rates=ramp_rates,
        hold_times=hold_times,
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

    ss_df = load_and_process(exp.experiment_id)
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
        
        exp = sample_info()

        exp = pretreatment(
            exp=exp,
            target_temps=[400],
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

        exp = run_steady_state(
            exp=exp,
            target_temps=[120,140,160,180,200,225,250,275,300,350,400],
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

        standby(exp) if standby else exp.close()

    def experiment_2(standby: bool = True) -> None:
        
        exp = sample_info()

        exp = pretreatment(
            exp=exp,
            target_temps=[400],
            ramp_rates=[10.0],
            hold_times=[30.0],
            gas_flow={
                "total_flow_rate": 410,
                "gas_concentrations": {
                    "h2": 9300.0,
                    "nh3": 0.0,
                    "no": 350.0,
                    "o2": 2.0,
                    "h2o": 20.0,
                    },
                },
        )

        exp = run_steady_state(
            exp=exp,
            target_temps=[120,140,160,180,200,225,250,275,300,350,400],
            ramp_rates=[10.0],
            hold_times=[30.0],
            gas_flow={
                "total_flow_rate": 410,
                "gas_concentrations": {
                    "h2": 9300.0,
                    "nh3": 0.0,
                    "no": 350.0,
                    "o2": 2.0,
                    "h2o": 20.0,
                },
            },
        )

        standby(exp) if standby else exp.close()


    experiment_1(standby=False)
    experiment_2()


"""
Open Items:
1. the mks program didn't save?? Check box was unchecked.
2. Make the MFC valves "Closed" if flow is 0.
3. if sample info exists, don't write.
4. introduce hold argument in run_steady_state()?
5. get rid of error message in .json
6. all temps except temp_actual should be null when _mks_on=True
7. Don't rely on steady-state detection. Just write the times and use those in analysis.
8. Create single temperature setpoint.
"""
