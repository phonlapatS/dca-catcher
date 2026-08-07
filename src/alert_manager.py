import logging
import re
from typing import Tuple, Optional
from sqlalchemy import select

from src.database import Database, Watchlist, User

logger = logging.getLogger(__name__)

class AlertManager:
    def __init__(self, db: Database):
        self.db = db

    def parse_zones(self, target_zones_str: str):
        # Expected format: "150.0 (Low Risk), 140.0 (Moderate)"
        # Or maybe it comes as a raw string. Let's assume comma-separated list of `price (label)`
        zones = []
        parts = target_zones_str.split(',')
        for p in parts:
            p = p.strip()
            if not p:
                continue
            # Regex to match "150.0 (Low Risk)"
            m = re.match(r'^([\d\.]+)\s*\((.*?)\)$', p)
            if m:
                zones.append({
                    "price": float(m.group(1)),
                    "label": m.group(2),
                    "raw": p
                })
        # sort by price descending
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
            
        active_zone_str = active_zone["raw"]

        async with self.db.session() as session:
            stmt = select(Watchlist).join(User, Watchlist.user_id == User.id).where(
                User.telegram_id == user_id, 
                Watchlist.symbol == symbol
            )
            res = await session.execute(stmt)
            watchlist_item = res.scalar_one_or_none()

            if not watchlist_item:
                return False, None

            if watchlist_item.last_notified_zone == active_zone_str:
                return False, None

            watchlist_item.last_notified_zone = active_zone_str
            await session.commit()
            
            # Format message
            next_target_info = f" {next_zone['price']} ({next_zone['label']})" if next_zone else " N/A (N/A)"
            
            msg = (
                f"ท่านสามารถเข้าซื้อที่ราคาเป้าหมายตอนนี้ได้แล้ว {active_zone['price']} ({active_zone['label']}) "
                f"รอดูสถาณการณ์ว่าราคาจะขยับขึ้นหรือลงต่อที่เป้าหมายถัดไป{next_target_info}"
            )
            return True, msg
