"""Command-line entry point for the IoT device simulator."""

from __future__ import annotations

import sys

from .config import load_config
from .publisher import DeviceSimulator


def main() -> int:
    try:
        simulator = DeviceSimulator(load_config())
        simulator.run()
    except KeyboardInterrupt:
        print("\nShutdown requested.")
    except (OSError, TimeoutError, RuntimeError, ValueError) as exc:
        print(f"Simulator error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
