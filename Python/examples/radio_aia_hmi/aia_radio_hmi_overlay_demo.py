"""Public-API recipe for the AIA/radio/HMI overlay command.

This real-data workflow remains behind a parity boundary.  The short recipe
therefore delegates to the packaged command contract, which reports the
boundary without importing or running the historical scientific renderer.
The complete 1797-line implementation is retained under ``examples/history``.
"""

from __future__ import annotations

from collections.abc import Sequence

from solar_toolkit.radio.overlay_cli import main as run_overlay_command

REQUIRES_LOCAL_DATA = True


def main(argv: Sequence[str] | None = None) -> int:
    """Delegate to the packaged overlay command contract."""

    return run_overlay_command(argv)


if __name__ == "__main__":
    raise SystemExit(main())
