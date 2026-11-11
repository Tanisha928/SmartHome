"""Map catalog entries and model confidence to alert severity."""

from __future__ import annotations

from decimal import Decimal

from app.alerts.catalog import get_rule


class SeverityMapper:
    @staticmethod
    def map(category: str, sound_type: str, confidence: float | Decimal) -> str:
        """Return severity using the catalog's inclusive 0.90 boundary."""

        rule = get_rule(sound_type)
        if rule.category != category:
            raise ValueError(f"Category mismatch for {sound_type}: expected {rule.category}")
        if rule.downgrade_below is not None and float(confidence) < rule.downgrade_below:
            assert rule.downgraded_severity is not None
            return rule.downgraded_severity
        return rule.default_severity
