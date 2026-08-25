"""Run the credential-free Affiliate-Mate v1 golden acceptance path."""

from __future__ import annotations

import argparse
import json
import tempfile
import time
from pathlib import Path

from affiliate_mate.acceptance import run_golden_acceptance


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-seconds", type=float, default=20.0)
    parser.add_argument("--workspace", type=Path)
    args = parser.parse_args()
    if args.max_seconds <= 0:
        raise SystemExit("--max-seconds must be > 0")

    started = time.perf_counter()
    if args.workspace is None:
        with tempfile.TemporaryDirectory(prefix="affiliate-mate-v1-") as raw:
            report = run_golden_acceptance(Path(raw))
    else:
        report = run_golden_acceptance(args.workspace)
    elapsed = time.perf_counter() - started
    report["wall_seconds"] = round(elapsed, 6)
    report["max_wall_seconds"] = args.max_seconds
    report["within_budget"] = elapsed <= args.max_seconds
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] and report["within_budget"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
