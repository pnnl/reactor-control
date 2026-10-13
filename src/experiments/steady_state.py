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
    is_new_sample: bool,
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
            is_new_sample=is_new_sample,
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

        exp.log_step()

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
        persist_ss_ranges=True,
    )

    exp.stop_data_collection()

    load_and_process(exp.experiment_id, ss_ranges=exp.ss_ranges)
    exp.export_to_z_drive()

    return exp


def standby(exp: Experiment, standby_temp: float = 120) -> None:
    """Set system to standby mode after experiment."""

    exp.standby(temperature=standby_temp)
    exp.close()


if __name__ == "__main__":

    def nn_exp1(standby: bool = True) -> None:
        exp = sample_info(
            batch_id="cu-ssz-13-si-al-6, nn2063-4",
            mass_mg=200.0,
            operator="nelson",
            composition="cu-ssz-13, Pt/Al2O3(80)-ZrO2(20)",
            metal="Cu, Pt",
            support="ssz-13, Al2O3(80)-ZrO2(20)",
            metal_loading_wt_percent=0.1,
            mesh_size="30-60",
            is_new_sample=True,
            synthesis_method=", (NH3)4Pt(NO3)2 (100 uL, 1 wt. %) solution added to 0.5 g of Al2O3(80)-ZrO2(20). Leave at RT for 48h. Dry at 60 °C for 2 h. Not calcined.",
        )

        exp = pretreatment(
            exp=exp,
            target_temps=[500, 120],
            ramp_rates=[10],
            hold_times=[60*1.75, 0],
            gas_flows=[
                {
                    "total_flow_rate": 200,
                    "gas_concentrations": {
                        "h2": 0.0,
                        "nh3": 0.0,
                        "no": 0.0,
                        "o2": 40.0,
                        "h2o": 0.0,
                        "n2": 0.0
                    },
                }
            ],
        )

        exp = run_steady_state(
            exp=exp,
            target_temps=[120, 140, 160, 180, 200, 250, 300, 350, 400],
            ramp_rates=[10],
            hold_times=[60, 30],
            gas_flow={
                "total_flow_rate": 410,
                "gas_concentrations": {
                    "h2": 9300.0,
                    "nh3": 0.0,
                    "no": 350.0,
                    "o2": 10.0,
                    "h2o": 20.0,
                },
            },
        )

        exp.standby() if standby else exp.close()

    def nn_exp2(standby: bool = True) -> None:
        exp = sample_info(
            batch_id="cu-ssz-13-si-al-6, nn2063-4",
            mass_mg=200.0,
            operator="nelson",
            composition="cu-ssz-13, Pt/Al2O3(80)-ZrO2(20)",
            metal="Cu, Pt",
            support="ssz-13, Al2O3(80)-ZrO2(20)",
            metal_loading_wt_percent=0.1,
            mesh_size="30-60",
            is_new_sample=False,
            synthesis_method=", (NH3)4Pt(NO3)2 (100 uL, 1 wt. %) solution added to 0.5 g of Al2O3(80)-ZrO2(20). Leave at RT for 48h. Dry at 60 °C for 2 h. Not calcined.",
        )

        exp = pretreatment(
            exp=exp,
            target_temps=[500, 120],
            ramp_rates=[10.0],
            hold_times=[1.25 * 60, 0],
            gas_flows=[
                {
                    "total_flow_rate": 200,
                    "gas_concentrations": {
                        "h2": 10000.0,
                        "nh3": 0.0,
                        "no": 2800.0,
                        "o2": 0.0,
                        "h2o": 0.0,
                        "n2": 0.0
                    },
                },
            ],
        )

        exp = run_steady_state(
            exp=exp,
            target_temps=[120, 140, 160, 180, 200, 250, 300, 350, 400],
            ramp_rates=[10],
            hold_times=[60, 30],
            gas_flow={
                "total_flow_rate": 410,
                "gas_concentrations": {
                    "h2": 9300.0,
                    "nh3": 0.0,
                    "no": 350.0,
                    "o2": 10.0,
                    "h2o": 20.0,
                },
            },
        )

        exp.standby() if standby else exp.close()

    def cs_exp1(standby: bool = True) -> None:
        exp = sample_info(
            batch_id="",
            mass_mg=50, #220.0,
            operator="DJD",
            composition="2% Cu-CHA PIDC 4.6",#"Pt-Al2O3-Cummins-ASC",
            metal="Cu",
            support="CHA",
            metal_loading_wt_percent=2.0,
            mesh_size="60-80",
            is_new_sample=True,
            synthesis_method="SSIE",
        )

        exp = pretreatment(
            exp=exp,
            target_temps=[120],
            ramp_rates=[10.0],
            hold_times=[10],
            gas_flows=[
                {
                    "total_flow_rate": 320, #sccm
                    "gas_concentrations": {
                        "h2": 600.0, # ppm
                        "nh3": 0.0, # ppm
                        "no": 0.0, # ppm
                        "o2": 0.0, # pct
                        "h2o": 0.0, # pct
                    },
                },
            ],
        )

        exp = run_steady_state(
            exp=exp,
            target_temps=[120, 500, 120],#400, 350, 300, 290, 270, 260, 250, 240, 230, 220, 210, 200, 190, 170, 150],
            ramp_rates=[10],
            hold_times=[30,30],
            gas_flow={
                "total_flow_rate": 320, # mL/min
                "gas_concentrations": {
                    "h2": 0.0,
                    "nh3": 0.0,
                    "no": 0.0,
                    "o2": 0.0,
                    "h2o": 0.0,
                },
            },
        )

        exp.standby() if standby else exp.close()

    def cs_exp2(standby: bool = True) -> None:
        exp = sample_info(
            batch_id="",
            mass_mg=50.0,
            operator="CS",
            composition="Pt-only/Al2O3",
            metal="Pt",
            support="Al2O3",
            metal_loading_wt_percent=0.1,
            mesh_size="60-80",
            is_new_sample=False,
            synthesis_method="",
        )

        exp = pretreatment(
            exp=exp,
            target_temps=[450, 120],
            ramp_rates=[10.0],
            hold_times=[1.0, 0],
            gas_flows=[
                {
                    "total_flow_rate": 210, #sccm
                    "gas_concentrations": {
                        "h2": 1000.0, # ppm
                        "nh3": 0.0, # ppm
                        "no": 2800.0, # ppm
                        "o2": 0.0, # pct
                        "h2o": 0.0, # pct
                        "n2": 0.0
                    },
                },
            ],
        )

        exp = run_steady_state(
            exp=exp,
            target_temps=[120, 140, 160, 180, 200, 250, 300, 350, 400],
            ramp_rates=[10],
            hold_times=[60, 30],
            gas_flow={
                "total_flow_rate": 410,
                "gas_concentrations": {
                    "h2": 9300.0,
                    "nh3": 0.0,
                    "no": 350.0,
                    "o2": 10.0,
                    "h2o": 20.0,
                },
            },
        )

        exp.standby() if standby else exp.close()

    def test(standby: bool = True) -> None:
        exp = sample_info(
            batch_id="test",
            mass_mg=50.0,
            operator="nelson",
            composition="Pd/Al2O3",
            metal="Pd",
            support="g-Al2O3",
            metal_loading_wt_percent=0.1,
            mesh_size="30-60",
            is_new_sample=False,
            synthesis_method="",
        )

        exp = pretreatment(
            exp=exp,
            target_temps=[120],
            ramp_rates=[10.0],
            hold_times=[1],
            gas_flows=[
                {
                    "total_flow_rate": 410,
                    "gas_concentrations": {
                        "h2": 0.0,
                        "nh3": 0.0,
                        "no": 0.0,
                        "o2": 10.0,
                        "h2o": 0.0,
                    },
                },
            ],
        )

        exp = run_steady_state(
            exp=exp,
            target_temps=[120],
            ramp_rates=[10.0],
            hold_times=[1],
            gas_flow={
                "total_flow_rate": 410,
                "gas_concentrations": {
                    "h2": 0.0,
                    "nh3": 0.0,
                    "no": 0.0,
                    "o2": 10.0,
                    "h2o": 0.0,
                },
            },
        )

        exp.standby() if standby else exp.close()

    # nn_exp1(standby=False)
    # nn_exp2(standby=True)
    cs_exp1(standby=True)
    #cs_exp2(standby=True)
    # test()


"""
Open Items:
1. if sample info exists, don't write.
2. NO=0 writes to 0.1
3. Check NO2 and N2 selectivity/mean in analyze_ss.py
4. Step 0 on sequentially run still has residual flow from the previoius mfc, e.g. H2=47.8 when it should be 0.0

From GL
1. If the total flow rate cannot reach the set value, does it not set the MFC openings to the set values? I was using 350 ppm NO, 10% O2, and 6% H2O as pretreatment, only NO and O2 were set to the correct values, but not H2O (HPLC pump not turned on) and N2 (at the standby value of 10%)
    [answer]: I believe you were doing this in flow_control.py. You need to set safety_interlocks=False inside FlowControl, otherwise it raises error and skips H2O and N2.
"""
