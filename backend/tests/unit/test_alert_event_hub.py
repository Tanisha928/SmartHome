from __future__ import annotations

import asyncio

from app.alerts.event_publisher import AlertEventHub


class FakeWebSocket:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []

    async def send_json(self, event: dict[str, object]) -> None:
        self.events.append(event)


def test_alert_events_are_isolated_by_house() -> None:
    async def scenario() -> None:
        hub = AlertEventHub()
        house_one = FakeWebSocket()
        house_two = FakeWebSocket()
        await hub.connect(1, house_one)  # type: ignore[arg-type]
        await hub.connect(2, house_two)  # type: ignore[arg-type]

        await hub.publish(1, {"type": "alert.created", "alert_id": 10})

        assert house_one.events == [{"type": "alert.created", "alert_id": 10}]
        assert house_two.events == []

    asyncio.run(scenario())
