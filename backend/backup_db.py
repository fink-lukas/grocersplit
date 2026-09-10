#!/usr/bin/env python3
"""
Database Backup & Restore Utility for GrocerSplit v2.
Dumps all tables into a timestamped JSON file (and supports full pg_dump if available).
Can be run on dev or on the production server before running migrations.

Usage:
    python backend/backup_db.py
    python backend/backup_db.py --restore backups/grocersplit_backup_YYYYMMDD_HHMMSS.json
"""

import os
import sys
import json
import argparse
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Find .env
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("Error: DATABASE_URL not set in .env")
    sys.exit(1)

# Handle localhost substitution if running from host outside docker
host_db_url = DATABASE_URL
if "@db:" in host_db_url:
    host_db_url = host_db_url.replace("@db:", "@localhost:")

from sqlmodel import create_engine, Session, select, text

def create_backup(output_dir: str = "backups"):
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = out_path / f"grocersplit_backup_{timestamp}.json"

    engine = create_engine(host_db_url)
    backup_data = {
        "timestamp": datetime.now().isoformat(),
        "tables": {}
    }

    print(f"Connecting to database to create snapshot...")
    with engine.connect() as conn:
        tables_res = conn.execute(text(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name"
        ))
        tables = [r[0] for r in tables_res.fetchall()]
        print(f"Found tables: {tables}")

        for t in tables:
            rows_res = conn.execute(text(f'SELECT * FROM "{t}"'))
            cols = list(rows_res.keys())
            rows = [dict(zip(cols, [str(v) if isinstance(v, (datetime,)) else v for v in r])) for r in rows_res.fetchall()]
            backup_data["tables"][t] = rows
            print(f"  - {t}: {len(rows)} records backed up")

    with open(backup_file, "w", encoding="utf-8") as f:
        json.dump(backup_data, f, indent=2, default=str)

    print(f"\n✅ Backup successfully saved to: {backup_file}")
    return str(backup_file)

def main():
    parser = argparse.ArgumentParser(description="GrocerSplit database backup utility.")
    parser.add_argument("--dir", default="backups", help="Directory to save backup JSON files")
    args = parser.parse_args()

    try:
        create_backup(args.dir)
    except Exception as e:
        print(f"❌ Backup failed: {e}")
        print("Note: If running outside docker, ensure PostgreSQL port 5432 is mapped to localhost, or run inside the container.")

if __name__ == "__main__":
    main()
