import logging
import re
from typing import Tuple, Optional
from sqlalchemy import select, func
import math

from src.database import Database, Watchlist, User

logger = logging.getLogger(__name__)


def _extract_zone_price(zone_str: Optional[str]) -> Optional[float]:
    if not zone_str:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)", zone_str)
    return float(match.group(1)) if match else None


class AlertManager:
    def __init__(self, db: Database):
        self.db = db

    @staticmethod
    def parse_zones(target_zones_str: str):
        if not target_zones_str:
            return []
        zones = []
        parts = target_zones_str.split(',')
        for p in parts:
            p = p.strip()
            if not p:
                continue
            m = re.match(r'^\$?([\d\.]+)(?:\s*\((.*?)\))?$', p)
            if m:
                try:
                    price = float(m.group(1))
                    label = m.group(2) if m.group(2) else "Target"
                    zones.append({
                        "price": price,
                        "label": label,
                        "raw": p
                    })
                except ValueError:
                    pass
        zones.sort(key=lambda x: x["price"], reverse=True)
        return zones

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
                is_same_zone(_extract_zone_price(item.last_notified_zone), active_zone["price"])
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
                    f"💬 ท่านสามารถพิจารณาเข้าซื้อที่ราคานี้ได้เลย หรือรอดูสถานการณ์ว่าราคาจะขยับลงต่อถึงเป้าหมายถัดไปที่ ${next_zone['price']} ({next_zone['label']}) หรือไม่"
                )
            else:
                msg = (
                    f"🎯 **เป้าหมายที่ถึงแล้ว:** ${active_zone['price']} ({active_zone['label']})\n\n"
                    f"💬 ท่านสามารถพิจารณาเข้าซื้อที่ราคานี้ได้เลยครับ (นี่คือเป้าหมายสุดท้ายที่คุณตั้งไว้)"
                )
            return True, msg

