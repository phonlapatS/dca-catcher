import logging
import re
from typing import Tuple, Optional
from sqlalchemy import select, func
import math

from src.database import Database, Watchlist, User
from src.models import TargetZone

logger = logging.getLogger(__name__)


class AlertManager:
    def __init__(self, db: Database):
        self.db = db

    @staticmethod
    def parse_zones(target_zones_str: str) -> list[dict]:
        """Parse target zones using the shared TargetZone model.

        Returns legacy dict format for backward compatibility with
        existing callers (sniper.py, bot.py).
        """
        zones = TargetZone.parse_many(target_zones_str)
        return [{"price": z.price, "label": z.label, "raw": f"${z.price} ({z.label})"} for z in zones]

    async def check_and_notify(self, user_id: int, symbol: str, current_price: float, target_zones_str: str) -> Tuple[bool, Optional[str]]:
        zones = self.parse_zones(target_zones_str)
        if not zones:
            return False, None

        # Determine which zone the current price is in.
        # It hits a zone if it's <= zone price.
        active_zone = None
        next_zone = None
        for i, z in enumerate(zones):
            if current_price <= z["price"]:
                active_zone = z
                if i + 1 < len(zones):
                    next_zone = zones[i+1]
            else:
                break
        
        if not active_zone:
            return False, None
            
        active_zone_str = f"{active_zone['price']}"

        async with self.db.session() as session:
            stmt = select(Watchlist).join(User, Watchlist.user_id == User.id).where(
                User.telegram_id == user_id, 
                func.upper(Watchlist.symbol) == symbol.upper()
            )
            res = await session.execute(stmt)
            watchlist_items = res.scalars().all()

            if not watchlist_items:
                return False, None

            # Hysteresis check using float comparison to prevent format mismatch
            def is_same_zone(z1, z2):
                if z1 is None or z2 is None:
                    return False
                return abs(z1 - z2) < 1e-5

            already_notified = any(
                is_same_zone(
                    TargetZone.to_prices(item.last_notified_zone)[0] if TargetZone.to_prices(item.last_notified_zone) else None,
                    active_zone["price"]
                )
                for item in watchlist_items
            )
            if already_notified:
                return False, None

            for item in watchlist_items:
                item.last_notified_zone = active_zone_str
            await session.commit()
            
            # Format message
            if next_zone:
                msg = (
                    f"🎯 **เป้าหมายที่ถึงแล้ว:** ${active_zone['price']} ({active_zone['label']})\n\n"
                    f"💬 ท่านสามารถเข้าซื้อที่ราคาเป้าหมายตอนนี้ได้แล้ว {active_zone['price']} ({active_zone['label']}) "
                    f"รอดูสถานการณ์ว่าราคาจะขยับลงต่อถึงเป้าหมายถัดไปที่ {next_zone['price']} ({next_zone['label']}) หรือไม่"
                )
            else:
                msg = (
                    f"🎯 **เป้าหมายที่ถึงแล้ว:** ${active_zone['price']} ({active_zone['label']})\n\n"
                    f"💬 ท่านสามารถเข้าซื้อที่ราคาเป้าหมายตอนนี้ได้แล้ว {active_zone['price']} ({active_zone['label']}) (นี่คือเป้าหมายสุดท้ายที่คุณตั้งไว้)"
                )
            return True, msg

