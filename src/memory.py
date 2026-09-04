"""
Memory module for DCA Catcher.

Provides clean OOP domain models and service classes for managing
user-specific chronological analysis snapshots (2+1 Memory Window)
to maintain analytical continuity and prevent AI hallucinations.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional
import logging
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import UserAnalysisMemory

logger = logging.getLogger(__name__)


@dataclass
class MemorySnapshot:
    """Domain model representing a single historical analysis checkpoint."""
    symbol: str
    analyzed_at: datetime
    price: float
    target_prices_str: Optional[str] = None
    thesis_status: Optional[str] = None
    thesis_summary: Optional[str] = None
    calibrated_confidence: Optional[int] = None
    market: str = "US"

    @property
    def days_ago(self) -> int:
        """Returns number of days elapsed since this snapshot."""
        now = datetime.now(timezone.utc)
        tz_aware = self.analyzed_at.replace(tzinfo=timezone.utc) if self.analyzed_at.tzinfo is None else self.analyzed_at
        delta = now - tz_aware
        return max(0, delta.days)


class MemoryManager:
    """Manages retrieval, formatting, and persistence of User Analysis Memory."""

    @staticmethod
    async def get_recent_timeline(
        session: AsyncSession,
        user_id: int,
        symbol: str,
        limit: int = 2
    ) -> List[MemorySnapshot]:
        """
        Retrieves the last N snapshots for a specific user and symbol,
        sorted chronologically ascending (T-2, T-1) for timeline generation.
        """
        try:
            query = (
                select(UserAnalysisMemory)
                .where(
                    UserAnalysisMemory.user_id == user_id,
                    UserAnalysisMemory.symbol == symbol.upper()
                )
                .order_by(desc(UserAnalysisMemory.analyzed_at))
                .limit(limit)
            )
            result = await session.execute(query)
            rows = result.scalars().all()
            
            # Convert ORM objects to Domain models and sort chronologically (oldest -> newest)
            snapshots = [
                MemorySnapshot(
                    symbol=r.symbol,
                    analyzed_at=r.analyzed_at,
                    price=r.price_at_analysis,
                    target_prices_str=r.target_prices_str,
                    thesis_status=r.thesis_status,
                    thesis_summary=r.thesis_summary,
                    calibrated_confidence=r.calibrated_confidence,
                    market=r.market
                )
                for r in rows
            ]
            snapshots.reverse()
            return snapshots
        except Exception as e:
            logger.error(f"Error fetching memory timeline for user={user_id}, symbol={symbol}: {e}")
            return []

    @staticmethod
    def format_timeline_prompt(snapshots: List[MemorySnapshot]) -> str:
        """
        Formats chronological snapshots into a structured string prompt for the LLM.
        If no history exists, returns a clear Cold Start notice.
        """
        if not snapshots:
            return "ไม่มีประวัติการสแกนเดิมในระบบ (First-time / Cold Start Scan)"

        lines = []
        n = len(snapshots)
        for idx, snap in enumerate(snapshots):
            stage_name = f"T-{n - idx}"  # e.g., T-2, T-1
            time_str = f"{snap.days_ago} วันก่อน" if snap.days_ago > 0 else "ก่อนหน้านี้"
            status_str = f" [สถานะ: {snap.thesis_status}]" if snap.thesis_status else ""
            summary_str = f": {snap.thesis_summary}" if snap.thesis_summary else ""
            targets_str = f" | เป้าหมาย: {snap.target_prices_str}" if snap.target_prices_str else ""
            
            line = f"- {stage_name} ({time_str} @ ${snap.price:,.2f}){status_str}{targets_str}{summary_str}"
            lines.append(line)

        return "\n".join(lines)

    @staticmethod
    async def save_memory_snapshot(
        session: AsyncSession,
        user_id: int,
        symbol: str,
        price: float,
        target_prices_str: Optional[str] = None,
        thesis_status: Optional[str] = None,
        thesis_summary: Optional[str] = None,
        calibrated_confidence: Optional[int] = None,
        market: str = "US"
    ) -> Optional[UserAnalysisMemory]:
        """
        Persists a new analysis memory snapshot for a user.
        """
        try:
            memory = UserAnalysisMemory(
                user_id=user_id,
                symbol=symbol.upper(),
                market=market,
                price_at_analysis=price,
                target_prices_str=target_prices_str,
                thesis_status=thesis_status or "CONTINUING",
                thesis_summary=thesis_summary,
                calibrated_confidence=calibrated_confidence,
                analyzed_at=datetime.now(timezone.utc)
            )
            session.add(memory)
            await session.commit()
            logger.info(f"Saved memory snapshot for user={user_id}, symbol={symbol}, price=${price:.2f}")
            return memory
        except Exception as e:
            logger.error(f"Failed to save memory snapshot for user={user_id}, symbol={symbol}: {e}")
            await session.rollback()
            return None
