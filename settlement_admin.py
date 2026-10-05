#!/usr/bin/env python3
"""Admin-only settlement controls; never delegates operations to the model."""
from __future__ import annotations

import argparse
import json
import logging
import os
import time
from pathlib import Path

from settlement import BuildingError, StructureManager


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    root.add_argument("--registry", default=os.getenv("DIRECTOR_STRUCTURES", "config/structures.json"))
    root.add_argument("--config", default=os.getenv("DIRECTOR_SETTLEMENT", "config/settlement.json"))
    root.add_argument("--database", default=os.getenv("DIRECTOR_DATABASE", "director_settlement.sqlite3"))
    root.add_argument("--dry-run", action="store_true", default=os.getenv("DIRECTOR_DRY_RUN", "0") == "1")
    sub = root.add_subparsers(dest="operation", required=True)
    listing = sub.add_parser("list")
    listing.add_argument("subject", choices=["structures", "plots"])
    showing = sub.add_parser("show")
    showing.add_argument("subject", choices=["settlement"])
    construct = sub.add_parser("construct")
    construct.add_argument("structure")
    construct.add_argument("plot", nargs="?")
    construct.add_argument("--owner")
    construct.add_argument("--reason", default="Admin construction")
    construct.add_argument("--wait", action="store_true", help="Advance stages until this build finishes (admin process only)")
    upgrade = sub.add_parser("upgrade")
    upgrade.add_argument("plot")
    upgrade.add_argument("structure")
    upgrade.add_argument("--owner")
    upgrade.add_argument("--reason", default="Admin upgrade")
    upgrade.add_argument("--wait", action="store_true")
    removal = sub.add_parser("remove", help="Remove only an unchanged Director building; rejects player edits and sensitive blocks")
    removal.add_argument("subject", choices=["structure"])
    removal.add_argument("plot")
    grant = sub.add_parser("grant")
    grant.add_argument("subject", choices=["settlement-xp"])
    grant.add_argument("amount", type=int)
    sub.add_parser("initialize", help="Validate and start configured one-time starter construction")
    sub.add_parser("tick", help="Advance due durable construction stages once")
    return root


def main(argv: list[str] | None = None, *, command=None) -> int:
    args = parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if command is None:
        from director import rcon
        command = rcon
    manager = None
    try:
        manager = StructureManager(Path(args.registry), Path(args.config), Path(args.database), command, dry_run=args.dry_run)
        if args.operation == "list":
            result = manager.list_structures() if args.subject == "structures" else manager.list_plots()
        elif args.operation == "show":
            result = manager.show_settlement()
        elif args.operation == "construct":
            result = manager.place(args.structure, args.plot, owner=args.owner, reason=args.reason)
        elif args.operation == "upgrade":
            result = manager.upgrade(args.plot, args.structure, owner=args.owner, reason=args.reason)
        elif args.operation == "remove":
            result = manager.remove(args.plot)
        elif args.operation == "grant":
            result = manager.grant_xp(args.amount)
        elif args.operation == "initialize":
            result = manager.initialize(force=True)
        else:
            result = manager.tick()
        print(json.dumps(result, indent=2))
        if getattr(args, "wait", False) and not args.dry_run and result.get("pending"):
            plot_id = result["plot_id"]
            while True:
                events = manager.tick()
                if events:
                    print(json.dumps(events, indent=2))
                plot = next(p for p in manager.list_plots() if p["id"] == plot_id)
                if plot["status"] not in ("reserved", "upgrading"):
                    return 0 if plot["status"] == "occupied" else 1
                time.sleep(0.25)
        results = result if isinstance(result, list) else [result]
        return 1 if any(isinstance(item, dict) and item.get("success") is False for item in results) else 0
    except (BuildingError, OSError, ValueError) as exc:
        print(json.dumps({"success": False, "error": str(exc), "dry_run": args.dry_run}))
        return 1
    finally:
        if manager is not None:
            manager.close()


if __name__ == "__main__":
    raise SystemExit(main())
