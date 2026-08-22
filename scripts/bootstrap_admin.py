#!/usr/bin/env python
"""
TourSafe Secure Initial Administrator Bootstrap Tool.
Creates the root authority administrator account safely using environment variables
or interactive prompts. Does not hardcode credentials.
"""

import argparse
import asyncio
import getpass
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.core.database import get_database, close_database
from app.core.security import get_password_hash


async def bootstrap_admin(email: str, password: str, full_name: str, jurisdiction_id: str):
    db = get_database()
    try:
        # Check if authority / admin user already exists
        existing = await db.users.find_one({"email": email})
        if existing:
            print(f"⚠️  User with email '{email}' already exists.")
            return False

        hashed_password = get_password_hash(password)
        admin_doc = {
            "id": str(uuid.uuid4()),
            "email": email.lower().strip(),
            "password_hash": hashed_password,
            "full_name": full_name,
            "role": "admin",
            "jurisdiction_id": jurisdiction_id,
            "is_active": True,
            "is_verified": True,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "bootstrapped": True,
        }

        await db.users.insert_one(admin_doc)
        print(f"✅ Successfully bootstrapped administrator account: {email}")
        return True
    finally:
        await close_database()


def main():
    parser = argparse.ArgumentParser(description="TourSafe Administrator Bootstrap Tool")
    parser.add_argument("--email", default=os.getenv("ADMIN_BOOTSTRAP_EMAIL"), help="Admin email address")
    parser.add_argument("--full-name", default=os.getenv("ADMIN_BOOTSTRAP_NAME", "Root Administrator"), help="Admin full name")
    parser.add_argument("--jurisdiction", default=os.getenv("ADMIN_BOOTSTRAP_JURISDICTION", "GLOBAL"), help="Jurisdiction ID")

    args = parser.parse_args()

    email = args.email
    if not email:
        email = input("Enter admin email: ").strip()

    password = os.getenv("ADMIN_BOOTSTRAP_PASSWORD")
    if not password:
        password = getpass.getpass("Enter admin password (min 12 chars): ")
        confirm = getpass.getpass("Confirm admin password: ")
        if password != confirm:
            print("❌ Passwords do not match.")
            sys.exit(1)

    if len(password) < 12:
        print("❌ Password must be at least 12 characters.")
        sys.exit(1)

    asyncio.run(bootstrap_admin(email, password, args.full_name, args.jurisdiction))


if __name__ == "__main__":
    main()
