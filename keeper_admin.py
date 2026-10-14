#!/usr/bin/env python3
"""Read-only Keeper progress and guarded temple-upgrade inspection."""
from __future__ import annotations

import argparse
import contextlib
import importlib
import json
import os
import sys

from keeper import KeeperError, KeeperUncertain, status


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    root.add_argument("--state", help="Quest-state JSON path (defaults to DIRECTOR_STATE)")
    sub = root.add_subparsers(dest="operation", required=True)
    showing = sub.add_parser("show", help="Read saved progress; no RCON connection is needed")
    showing.add_argument("--keeper-id", help="Select a saved Keeper; otherwise show the entire registry")
    preview = sub.add_parser("preview", help="Inspect the configured original temple using read-only RCON probes")
    preview.add_argument("--keeper-id", help="Must match the explicitly configured original temple")
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    # Set this before Director's import-time configuration or migration executes.
    os.environ["DIRECTOR_DRY_RUN"] = "1"
    if args.state is not None:
        os.environ["DIRECTOR_STATE"] = args.state
    try:
        with contextlib.redirect_stdout(sys.stderr):
            director = importlib.import_module("director")
            if not director.DRY_RUN:
                raise KeeperError("Keeper inspection requires a fresh read-only Director import")
            state = director.load_state()
            if args.operation == "show":
                selected = args.keeper_id
                if selected is None and len(state.keepers) == 1:
                    selected = next(iter(state.keepers))
                result = status(state.keepers, selected)
                result.update(success=True, dry_run=True, enabled=director.KEEPER_ENABLED, state_path=str(director.STATE_PATH))
            else:
                controller = director.keeper_controller(state, persist=False)
                if controller is None:
                    raise KeeperError("Keeper progression is disabled; preview requires explicit temple configuration")
                if args.keeper_id is not None and args.keeper_id != controller.keeper_id:
                    raise KeeperError("Preview cannot select a different temple from the explicitly configured original Keeper")
                if not controller.dry_run:
                    raise KeeperError("Read-only preview requires a dry-run Keeper controller")
                result = controller.preview(state.keepers)
                result["state_path"] = str(director.STATE_PATH)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result.get("success", True) else 1
    except (KeeperError, KeeperUncertain, OSError, ValueError) as exc:
        print(json.dumps({"success": False, "dry_run": True, "error": str(exc)}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
