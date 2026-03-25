"""Example usage of visualization module.

Demonstrates loading experiment data and creating plots.

Run from project root:
    python -m src.visualization.example
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt

SRC_PATH = Path(__file__).resolve().parent.parent.parent
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from src.analyze import load_and_process
from src.visualization import plot_steady_state


def main():
    # Load and process experiment data (data_root and save handled internally)
    experiment_id = "20260323_161630_steady-state"
    ss_df, output_path = load_and_process(experiment_id)

    # Plot steady-state data
    fig, _ = plot_steady_state(ss_df)
    plt.show()

    # Print steady-state data table
    print(ss_df)
    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
