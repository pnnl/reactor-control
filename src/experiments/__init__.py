"""Experiments layer for reactor control.

Provides an Experiment class for writing flexible experiment scripts.

Example:
    from src.experiments import Experiment, Sample

    exp = Experiment(name="My Experiment", connect_devices=False)
    try:
        exp.set_sample(Sample(...))
        exp.set_temperature(target=200, rate=5)
        exp.hold(minutes=30)
    finally:
        exp.close()
"""

from ._api import Experiment
from ._api import Sample

__all__ = [
    "Experiment",
    "Sample",
]
