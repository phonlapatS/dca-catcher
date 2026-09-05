from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, select, func, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Mapped, declarative_base, mapped_column, relationship

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    remark: Mapped[str | None] = mapped_column(String(255), nullable=True) # Admin note or alias
    risk_profile: Mapped[str | None] = mapped_column(String(255), nullable=True) # Stores user investment style
    notify_dm: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")  # True = DM, False = group tag
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now())
    watchlists: Mapped[list["Watchlist"]] = relationship("Watchlist", back_populates="user", cascade="all, delete-orphan")


class Watchlist(Base):
    __tablename__ = "watchlists"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    user: Mapped["User"] = relationship("User", back_populates="watchlists")
    symbol: Mapped[str] = mapped_column(String)
    market: Mapped[str] = mapped_column(String)
    target_zones_str: Mapped[str | None] = mapped_column(String, nullable=True)
    last_notified_zone: Mapped[str | None] = mapped_column(String, nullable=True)


class PortfolioTransaction(Base):
    __tablename__ = "portfolio_transactions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    symbol: Mapped[str] = mapped_column(String, index=True)
    action: Mapped[str] = mapped_column(String)  # 'BUY' or 'SELL'
    price: Mapped[float] = mapped_column(Float)
    shares: Mapped[float] = mapped_column(Float)
    transaction_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now())


class Signal(Base):
    __tablename__ = "signals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String)
    grade: Mapped[int] = mapped_column(Integer)
    confidence: Mapped[int] = mapped_column(Integer)
    advice: Mapped[str] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )


class UserAnalysisMemory(Base):
    """Stores chronological analysis snapshots per user and symbol (2+1 Memory Window)."""
    __tablename__ = "user_analysis_memories"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    user: Mapped["User"] = relationship("User")
    symbol: Mapped[str] = mapped_column(String, index=True)
    market: Mapped[str] = mapped_column(String, default="US")
    analyzed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )
    price_at_analysis: Mapped[float] = mapped_column(Float)
    target_prices_str: Mapped[str | None] = mapped_column(String, nullable=True)
    thesis_status: Mapped[str | None] = mapped_column(String, nullable=True)  # CONTINUING, INVALIDATED, NEW_CATALYST, RESOLVED
    thesis_summary: Mapped[str | None] = mapped_column(String, nullable=True) # Concise 1-sentence thesis
    calibrated_confidence: Mapped[int | None] = mapped_column(Integer, nullable=True) # 0-100%


class SeenCatalyst(Base):
    """Tracks processed news catalyst hashes to prevent duplicate evaluation (Zero-Token Deduplication)."""
    __tablename__ = "seen_catalysts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    headline_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    headline: Mapped[str] = mapped_column(Text)
    publisher: Mapped[str | None] = mapped_column(String(255), nullable=True)
    seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)




class FundamentalHealth(Base):
    """Stores historical fundamental health data (P/E, EPS, Margins) to track growth trends."""
    __tablename__ = 'fundamental_health'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String, index=True, nullable=False)
    record_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    trailing_pe: Mapped[float | None] = mapped_column(Float, nullable=True)
    forward_pe: Mapped[float | None] = mapped_column(Float, nullable=True)
    eps_ttm: Mapped[float | None] = mapped_column(Float, nullable=True)
    revenue_growth: Mapped[float | None] = mapped_column(Float, nullable=True)
    profit_margin: Mapped[float | None] = mapped_column(Float, nullable=True)
    free_cash_flow: Mapped[float | None] = mapped_column(Float, nullable=True)
    debt_to_equity: Mapped[float | None] = mapped_column(Float, nullable=True)

class ScanCache(Base):
    __tablename__ = 'scan_cache'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String, index=True, nullable=False)
    scan_type: Mapped[str] = mapped_column(String, index=True, nullable=False)  # 'BASIC', 'DEEP_DIVE', 'NEWS'
    response_text: Mapped[str] = mapped_column(String, nullable=False)
    metadata_json: Mapped[str | None] = mapped_column(String, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class Database:

    """Manages async SQLAlchemy engine and session lifecycle."""

    def __init__(self, url: str):
        # Determine if it's postgres or sqlite to apply pool settings
        if "postgresql" in url:
            self._engine = create_async_engine(
                url, 
                echo=False, 
                pool_pre_ping=True, 
                pool_recycle=1800,
                # Disable prepared statements cache if using PgBouncer
                connect_args={"server_settings": {"jit": "off"}}
            )
        else:
            self._engine = create_async_engine(url, echo=False)
            
        self._session_factory = async_sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )

    @property
    def engine(self):
        return self._engine

    async def create_tables(self):
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        # Auto-migrate: add missing columns for existing SQLite DBs
        async with self._engine.begin() as conn:
            for col, typ, default in [
                ("target_zones_str", "TEXT", None),
                ("last_notified_zone", "TEXT", None),
            ]:
                try:
                    await conn.execute(text(f"ALTER TABLE watchlists ADD COLUMN {col} {typ}"))
                except Exception:
                    pass
            for col, typ, default in [
                ("notify_dm", "INTEGER", "1"),
            ]:
                try:
                    await conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} {typ} DEFAULT {default}"))
                except Exception:
                    pass
            for col, typ, default in [
                ("remark", "TEXT", "NULL"),
            ]:
                try:
                    await conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} {typ} DEFAULT {default}"))
                except Exception:
                    pass
            for col, typ, default in [
                ("metadata_json", "TEXT", "NULL"),
            ]:
                try:
                    await conn.execute(text(f"ALTER TABLE seen_catalysts ADD COLUMN {col} {typ} DEFAULT {default}"))
                except Exception:
                    pass

    def session(self) -> AsyncSession:
        return self._session_factory()

    async def close(self):
        await self._engine.dispose()

    async def get_unique_watchlist_symbols(self, market: str = None) -> list[str]:
        async with self.session() as session:
            query = select(Watchlist.symbol).distinct()
            if market:
                query = query.where(Watchlist.market == market)
            result = await session.execute(query)
            return [row[0] for row in result.all()]

    async def record_seen_catalyst(
        self, headline_hash: str, symbol: str, headline: str, publisher: str | None = None, metadata_json: str | None = None
    ) -> bool:
        """Records a catalyst headline hash. Returns True if recorded, False if already exists."""
        import logging
        logger = logging.getLogger(__name__)
        async with self.session() as session:
            try:
                catalyst = SeenCatalyst(
                    headline_hash=headline_hash,
                    symbol=symbol.upper(),
                    headline=headline,
                    publisher=publisher,
                    metadata_json=metadata_json
                )
                session.add(catalyst)
                await session.commit()
                return True
            except Exception as e:
                logger.debug(f"Catalyst already seen or DB error for {symbol}: {e}")
                await session.rollback()
                return False

    
    async def get_cached_scan(self, symbol: str, scan_type: str) -> Optional[dict]:
        async with self.session() as session:
            now = datetime.now(timezone.utc)
            stmt = select(ScanCache).where(
                ScanCache.symbol == symbol,
                ScanCache.scan_type == scan_type,
                ScanCache.expires_at > now
            )
            result = (await session.execute(stmt)).scalar_one_or_none()
            if result:
                import json
                meta = json.loads(result.metadata_json) if result.metadata_json else None
                return {"response_text": result.response_text, "metadata": meta}
            return None

    async def set_cached_scan(self, symbol: str, scan_type: str, response_text: str, expires_in_hours: float = 2.0, metadata: dict = None):
        async with self.session() as session:
            import json
            from datetime import timedelta
            now = datetime.now(timezone.utc)
            expires = now + timedelta(hours=expires_in_hours)
            meta_str = json.dumps(metadata) if metadata else None

            # Upsert or replace old cache
            stmt = select(ScanCache).where(
                ScanCache.symbol == symbol,
                ScanCache.scan_type == scan_type
            )
            existing = (await session.execute(stmt)).scalar_one_or_none()

            if existing:
                existing.response_text = response_text
                existing.metadata_json = meta_str
                existing.expires_at = expires
                existing.created_at = now
            else:
                new_cache = ScanCache(
                    symbol=symbol,
                    scan_type=scan_type,
                    response_text=response_text,
                    metadata_json=meta_str,
                    expires_at=expires
                )
                session.add(new_cache)
            await session.commit()

    async def is_catalyst_seen(self, headline_hash: str) -> bool:
        """Checks whether a catalyst hash has already been processed."""
        async with self.session() as session:
            result = await session.execute(
                select(SeenCatalyst.id).where(SeenCatalyst.headline_hash == headline_hash)
            )
            return result.scalar_one_or_none() is not None

    async def cleanup_old_catalysts(self, retention_days: int = 30) -> int:
        """Delete seen_catalysts entries older than retention_days to prevent unbounded table growth."""
        import logging
        from datetime import timedelta
        from sqlalchemy import delete
        logger = logging.getLogger(__name__)
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        async with self.session() as session:
            stmt = delete(SeenCatalyst).where(SeenCatalyst.seen_at < cutoff)
            result = await session.execute(stmt)
            await session.commit()
            deleted = result.rowcount
            if deleted:
                logger.info(f"Cleaned up {deleted} old catalyst entries (>{retention_days} days)")
            return deleted

    async def get_user(self, telegram_id: int, username: str | None = None) -> User:
        """Get or create user safely. Handles race conditions with a try/except IntegrityError."""
        from sqlalchemy.exc import IntegrityError
        
        async with self.session() as session:
            stmt = select(User).where(User.telegram_id == telegram_id)
            res = await session.execute(stmt)
            user = res.scalar_one_or_none()
            
            if user:
                return user
                
            try:
                user = User(telegram_id=telegram_id, username=username)
                session.add(user)
                await session.commit()
                return user
            except IntegrityError:
                await session.rollback()
                # Race condition lost, another request created the user. Fetch it.
                res = await session.execute(stmt)
                return res.scalar_one()


def get_engine(url: str):
    return create_async_engine(url, echo=False)


def get_session_maker(engine):
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

