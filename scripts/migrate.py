#!/usr/bin/env python
"""
TourSafe Database Migration CLI Tool.
Usage:
    python scripts/migrate.py status
    python scripts/migrate.py up [--dry-run]
    python scripts/migrate.py rollback [--dry-run]
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.core.database import get_database, close_database
from app.core.migrations import migration_engine


async def main():
    parser = argparse.ArgumentParser(description="TourSafe Schema Migration CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Status
    subparsers.add_parser("status", help="Display status of all registered database migrations")

    # Up
    up_parser = subparsers.add_parser("up", help="Apply pending database migrations")
    up_parser.add_argument("--dry-run", action="store_true", help="Simulate migration without writing changes")

    # Rollback
    rb_parser = subparsers.add_parser("rollback", help="Roll back the most recent reversible migration")
    rb_parser.add_argument("--dry-run", action="store_true", help="Simulate rollback without writing changes")

    args = parser.parse_args()
    db = get_database()

    try:
        if args.command == "status":
            statuses = await migration_engine.get_status(db)
            print("================================================================================")
            print(f"{'VERSION':<18} | {'STATUS':<10} | {'REVERSIBLE':<10} | {'NAME'}")
            print("--------------------------------------------------------------------------------")
            for s in statuses:
                applied_str = "APPLIED" if s["applied"] else "PENDING"
                rev_str = "YES" if s["reversible"] else "NO"
                print(f"{s['version']:<18} | {applied_str:<10} | {rev_str:<10} | {s['name']}")
            print("================================================================================")

        elif args.command == "up":
            print(f"Applying pending migrations (Dry Run: {args.dry_run})...")
            executed = await migration_engine.run_up(db, dry_run=args.dry_run)
            if executed:
                print(f"Successfully processed {len(executed)} migrations: {', '.join(executed)}")
            else:
                print("Database is already up to date. No pending migrations.")

        elif args.command == "rollback":
            print(f"Rolling back last migration (Dry Run: {args.dry_run})...")
            reverted = await migration_engine.rollback_last(db, dry_run=args.dry_run)
            if reverted:
                print(f"Successfully reverted migration: {reverted}")
            else:
                print("No migrations available to revert.")

    finally:
        await close_database()


if __name__ == "__main__":
    asyncio.run(main())
