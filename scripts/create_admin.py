#!/usr/bin/env python3
"""Create an admin user. Usage: python scripts/create_admin.py email password [full_name]."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.core.security import hash_password
from app.persistence.pg.session import SessionLocal
from app.persistence.repositories.user_repo import UserRepository


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: create_admin.py <email> <password> [full_name]", file=sys.stderr)
        sys.exit(1)
    email, password = sys.argv[1], sys.argv[2]
    full_name = sys.argv[3] if len(sys.argv) > 3 else "Admin"
    if len(password) < 10:
        print("Password must be at least 10 characters", file=sys.stderr)
        sys.exit(1)

    db = SessionLocal()
    try:
        repo = UserRepository(db)
        existing = repo.get_by_email(email)
        if existing:
            existing.role = "admin"
            existing.password_hash = hash_password(password)
            db.commit()
            print(f"Updated existing user {email} to admin (id={existing.user_id})")
            return
        user = repo.create(
            email=email,
            password_hash=hash_password(password),
            full_name=full_name,
            role="admin",
        )
        db.commit()
        print(f"Created admin user_id={user.user_id} email={user.email}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
