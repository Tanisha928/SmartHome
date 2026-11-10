#!/usr/bin/env python3
"""Seed 1 admin, 2 owners, 3 houses with rooms/devices/residents (Phase 1)."""

from __future__ import annotations

import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.core.security import generate_device_api_key, hash_password
from sqlalchemy import select

from app.persistence.pg.models import Resident, Room
from app.persistence.pg.session import SessionLocal
from app.persistence.repositories.device_repo import DeviceRepository
from app.persistence.repositories.house_repo import HouseRepository
from app.persistence.repositories.user_repo import UserRepository


def main() -> None:
    db = SessionLocal()
    users = UserRepository(db)
    houses = HouseRepository(db)
    devices = DeviceRepository(db)

    try:
        admin = users.get_by_email("admin@smarthome.local") or users.create(
            email="admin@smarthome.local",
            password_hash=hash_password("admin-password-1"),
            full_name="Platform Admin",
            role="admin",
        )
        owner1 = users.get_by_email("owner1@smarthome.local") or users.create(
            email="owner1@smarthome.local",
            password_hash=hash_password("owner-password-1"),
            full_name="Alex Owner",
            phone="+15551001001",
            role="owner",
        )
        owner2 = users.get_by_email("owner2@smarthome.local") or users.create(
            email="owner2@smarthome.local",
            password_hash=hash_password("owner-password-2"),
            full_name="Blake Owner",
            phone="+15551001002",
            role="owner",
        )

        seed_houses = [
            {
                "address_line": "100 Maple St",
                "city": "Seattle",
                "state": "WA",
                "postal_code": "98101",
                "latitude": 47.6062,
                "longitude": -122.3321,
                "timezone": "America/Los_Angeles",
                "owner": owner1,
                "rooms": [("living", "Living Room"), ("kitchen", "Kitchen"), ("bedroom", "Master")],
            },
            {
                "address_line": "200 Oak Ave",
                "city": "Portland",
                "state": "OR",
                "postal_code": "97201",
                "latitude": 45.5152,
                "longitude": -122.6784,
                "timezone": "America/Los_Angeles",
                "owner": owner1,
                "rooms": [("living", "Family Room"), ("bath", "Bath")],
            },
            {
                "address_line": "300 Pine Rd",
                "city": "San Jose",
                "state": "CA",
                "postal_code": "95112",
                "latitude": 37.3382,
                "longitude": -121.8863,
                "timezone": "America/Los_Angeles",
                "owner": owner2,
                "rooms": [("living", "Living"), ("kitchen", "Kitchen")],
            },
        ]

        for i, spec in enumerate(seed_houses, start=1):
            existing = houses.find_by_address(spec["address_line"], spec["postal_code"])
            if existing:
                house = existing
            else:
                house = houses.create(
                    address_line=spec["address_line"],
                    city=spec["city"],
                    state=spec["state"],
                    postal_code=spec["postal_code"],
                    latitude=spec["latitude"],
                    longitude=spec["longitude"],
                    timezone=spec["timezone"],
                )
            houses.link_user(spec["owner"].user_id, house.house_id, "owner")

            db.add(
                Resident(
                    house_id=house.house_id,
                    full_name=f"Resident {i}",
                    birth_year=1945 + i,
                    care_notes="Seed resident",
                )
            )

            for room_type, label in spec["rooms"]:
                room = db.scalars(
                    select(Room).where(Room.house_id == house.house_id, Room.label == label)
                ).first()
                if room is None:
                    room = Room(house_id=house.house_id, room_type=room_type, label=label)
                    db.add(room)
                    db.flush()
                serial = f"SN-{house.house_id}-{room.room_id}-{secrets.token_hex(2)}"
                if not devices.find_by_serial(serial):
                    raw, digest, prefix = generate_device_api_key()
                    devices.create(
                        room_id=room.room_id,
                        house_id=house.house_id,
                        device_type="audio",
                        serial_no=serial,
                        label=f"{label} mic",
                        api_key_hash=digest,
                        api_key_prefix=prefix,
                    )
                    print(f"  device serial={serial} api_key={raw} (shown once)")

        db.commit()
        print(
            f"Seeded admin={admin.user_id}, owners={owner1.user_id},{owner2.user_id}, "
            f"houses={len(seed_houses)}"
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
