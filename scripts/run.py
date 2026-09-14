"""Workspace launcher for the same native product shipped by uv tool install."""

from pathlib import Path

from amplifier_tui.launcher import arguments as product_arguments
from amplifier_tui.launcher import main as product_main

ROOT = Path(__file__).resolve().parents[1]


def arguments(argv=None):
    return product_arguments(argv, workspace=ROOT)


def main():
    product_main(workspace=ROOT)


if __name__ == "__main__":
    main()
