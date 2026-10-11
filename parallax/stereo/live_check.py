"""Run the plane-sweep MVS live profile inside the Parallax runtime."""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

from pipeline.contracts import canonical_json
from stereo.plane_sweep import run_orbit_mvs_profile


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--profile", choices=("smoke", "full"), required=True)
    result.add_argument("--output", type=Path)
    return result


def main() -> int:
    args = parser().parse_args()
    if args.output is None:
        with tempfile.TemporaryDirectory(prefix=f"parallax-mvs-{args.profile}.") as temporary:
            summary = run_orbit_mvs_profile(Path(temporary) / "artifacts", args.profile)
    else:
        summary = run_orbit_mvs_profile(args.output, args.profile)
    print(canonical_json(summary).decode("ascii"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
