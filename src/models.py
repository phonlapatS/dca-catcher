"""
Shared domain models used across the DCA Catcher system.

This module is the Single Source of Truth for data structures
that are shared by multiple components (bot, sniper, alert_manager).
"""

import re
from dataclasses import dataclass


@dataclass
class TargetZone:
    """A single price target with an optional descriptive label.

    This is the canonical representation of target zones stored in the
    database ``Watchlist.target_zones_str`` column.  Every part of the
    codebase that needs to read or write target zones MUST go through
    this class to avoid divergent parsing logic.
    """

    price: float
    label: str = "Target"

    # ------------------------------------------------------------------
    # Serialisation helpers
    # ------------------------------------------------------------------

    @classmethod
    def parse_many(cls, raw: str | None) -> list["TargetZone"]:
        """Parse a comma-separated target zone string into a sorted list.

        Expected DB format examples:
            "$180.0 (Conservative), $170.0 (Moderate), $160.0 (Deep Value)"
            "$180.0, $170.0"
            "180.0"

        Returns a list sorted by price **descending** (highest first).
        """
        if not raw:
            return []

        zones: list[TargetZone] = []
        for part in raw.split(","):
            part = part.strip()
            if not part:
                continue
            match = re.match(r"^\$?([\d.]+)(?:\s*\((.*?)\))?$", part)
            if match:
                try:
                    price = float(match.group(1))
                    label = match.group(2) or "Target"
                    zones.append(cls(price=price, label=label))
                except ValueError:
                    continue

        zones.sort(key=lambda z: z.price, reverse=True)
        return zones

    @classmethod
    def to_prices(cls, raw: str | None) -> list[float]:
        """Convenience: parse and return only the price floats (descending)."""
        return [z.price for z in cls.parse_many(raw)]

    @classmethod
    def serialize(cls, zones: list["TargetZone"]) -> str:
        """Serialize a list of TargetZone back into the DB string format."""
        return ", ".join(f"${z.price} ({z.label})" for z in zones)
