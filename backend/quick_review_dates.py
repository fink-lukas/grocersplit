#!/usr/bin/env python3
"""
Quick Date & Store Review Utility for GrocerSplit v2.
Rapidly loops through receipts, pops open the receipt image, and prompts for the purchase date.
Runs locally on Linux / Desktop.

Usage:
    python backend/quick_review_dates.py
    python backend/quick_review_dates.py --all
    python backend/quick_review_dates.py --id 15
"""

import os
import sys
import subprocess
import shutil
from datetime import datetime
from pathlib import Path

# Find .env
env_path = Path(__file__).resolve().parent.parent / ".env"
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=env_path)
except ImportError:
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("'").strip('"')
                    if k not in os.environ:
                        os.environ[k] = v

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("Error: DATABASE_URL not set in .env")
    sys.exit(1)

# Handle localhost substitution if running from host outside docker
host_db_url = DATABASE_URL
if "@db:" in host_db_url:
    host_db_url = host_db_url.replace("@db:", "@localhost:")

# Ensure backend directory is on sys.path for direct script execution
backend_dir = str(Path(__file__).resolve().parent)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from sqlmodel import create_engine, Session, select
from app.models import Receipt, Item


def parse_user_date(user_input: str) -> datetime:
    """Parses DD.MM.YYYY, DD/MM/YYYY, or YYYY-MM-DD into a datetime object."""
    clean = user_input.strip()
    formats = [
        "%d.%m.%Y",
        "%d.%m.%y",
        "%d/%m/%Y",
        "%d/%m/%y",
        "%Y-%m-%d",
        "%Y.%m.%d",
        "%d-%m-%Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(clean, fmt)
        except ValueError:
            pass
    raise ValueError(f"Unknown date format: '{clean}'. Expected DD.MM.YYYY or YYYY-MM-DD.")


def open_image(image_path: Path):
    """Opens image in default viewer without blocking."""
    if not image_path.exists():
        print(f"  [!] Image file not found: {image_path}")
        return None

    str_path = str(image_path)
    # Prefer xdg-open on Linux
    if shutil.which("xdg-open"):
        return subprocess.Popen(["xdg-open", str_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    elif sys.platform == "darwin" and shutil.which("open"):
        return subprocess.Popen(["open", str_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        try:
            from PIL import Image
            img = Image.open(str_path)
            img.show()
            return None
        except Exception:
            return None


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Rapidly review and enter receipt purchase dates.")
    parser.add_argument("--all", action="store_true", help="Review all receipts, not just those missing dates")
    parser.add_argument("--id", type=int, help="Review a specific receipt by ID")
    args = parser.parse_args()

    engine = create_engine(host_db_url)

    # Determine base directory of workspace
    repo_root = Path(__file__).resolve().parent.parent

    with Session(engine) as session:
        query = select(Receipt).order_by(Receipt.id.asc())
        if args.id:
            query = query.where(Receipt.id == args.id)
        elif not args.all:
            query = query.where(Receipt.purchase_date.is_(None))

        receipts = session.exec(query).all()
        total = len(receipts)

        if total == 0:
            print("\n🎉 No receipts missing purchase dates! All up to date.")
            return

        print(f"\nFound {total} receipt(s) to review.")
        print("Commands: Enter date (e.g. 14.07.2024), Enter alone = skip, 's' = set store, 'q' = quit.\n")

        reviewed = 0
        updated = 0

        for idx, r in enumerate(receipts, 1):
            reviewed += 1
            cur_date = r.purchase_date.strftime("%d.%m.%Y") if r.purchase_date else "None"
            cur_store = r.merchant_name or r.description or "Unknown"

            print("=" * 65)
            print(f"[{idx}/{total}] Receipt #{r.id} | Total: €{r.total_amount/100:.2f} | Store: {cur_store}")
            print(f"  Uploaded: {r.created_at.strftime('%d.%m.%Y %H:%M')} | Current Purchase Date: {cur_date}")
            print(f"  Image: {r.image_path}")

            # Locate image file
            img_rel = r.image_path.lstrip("/")
            possible_paths = [
                repo_root / img_rel,
                repo_root / "backend" / img_rel,
                Path(img_rel),
            ]
            img_file = next((p for p in possible_paths if p.exists()), None)

            img_proc = None
            if img_file:
                img_proc = open_image(img_file)
            else:
                print(f"  [!] Warning: Could not locate image on disk.")

            while True:
                try:
                    val = input("  👉 Enter purchase date (DD.MM.YYYY) [Enter to skip, 'q' to quit]: ").strip()
                except (KeyboardInterrupt, EOFError):
                    print("\nExiting review tool.")
                    return

                if not val:
                    print("  -> Skipped.")
                    break
                elif val.lower() == "q":
                    print("\nExiting review tool. Progress saved.")
                    return
                elif val.lower() == "s":
                    new_store = input("     Enter store name (e.g. Hofer, Billa, Spar): ").strip()
                    if new_store:
                        r.merchant_name = new_store
                        session.add(r)
                        session.commit()
                        print(f"     ✅ Store updated to: {new_store}")
                    continue

                try:
                    dt = parse_user_date(val)
                    r.purchase_date = dt
                    session.add(r)
                    session.commit()
                    updated += 1
                    print(f"  ✅ Saved purchase date: {dt.strftime('%d.%m.%Y')}")
                    break
                except ValueError as e:
                    print(f"  ❌ {e}. Please try again (e.g. 05.09.2024).")

        print(f"\nFinished! Reviewed: {reviewed}, Updated: {updated}.")


if __name__ == "__main__":
    main()
