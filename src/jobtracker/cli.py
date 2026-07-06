"""CLI entry point.

  python -m jobtracker.cli run              # full daily run
  python -m jobtracker.cli dry-run          # fetch + classify, write/send nothing
  python -m jobtracker.cli preview          # run but print alert instead of sending
  python -m jobtracker.cli validate-firms   # enrich seed CSV by probing ATS endpoints
  python -m jobtracker.cli export           # dump DB to CSV
"""
import argparse, logging, os, sys
import yaml

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

def load_cfg(path="config/config.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)

def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(prog="jobtracker")
    p.add_argument("command", choices=["run", "dry-run", "preview", "validate-firms", "export"])
    p.add_argument("--config", default="config/config.yaml")
    p.add_argument("--only-priority", default="", help="validate-firms: only probe this priority level")
    p.add_argument("--limit", type=int, default=0, help="validate-firms: max firms to probe this run")
    p.add_argument("--force", action="store_true", help="validate-firms: re-probe verified firms too")
    p.add_argument("--no-probe", action="store_true", help="validate-firms: heuristics only, no network")
    args = p.parse_args()
    cfg = load_cfg(args.config)

    if args.command == "validate-firms":
        from .validate_firms import enrich
        enrich(cfg, probe=not args.no_probe, only_priority=args.only_priority,
               limit=args.limit, force=args.force)
    elif args.command == "export":
        from .db import DB
        db = DB(cfg["database"]["path"]); db.export_csv(cfg["database"]["export_csv"])
        print("exported to", cfg["database"]["export_csv"])
    else:
        from .runner import run
        if args.command == "preview":
            cfg["alerts"]["preview_only"] = True
        stats = run(cfg, dry_run=(args.command == "dry-run"))
        print(stats)
        sys.exit(1 if stats["failed_sources"] else 0)

if __name__ == "__main__":
    main()
