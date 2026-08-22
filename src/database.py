from datetime import datetime, timezone
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
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
    transaction_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Signal(Base):
    __tablename__ = "signals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String)
    grade: Mapped[int] = mapped_column(Integer)
    confidence: Mapped[int] = mapped_column(Integer)
    advice: Mapped[str] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
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
        DateTime, default=lambda: datetime.now(timezone.utc)
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
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class Database:

    """Manages async SQLAlchemy engine and session lifecycle."""

    def __init__(self, url: str):
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
        self, headline_hash: str, symbol: str, headline: str, publisher: str | None = None
    ) -> bool:
        """Records a catalyst headline hash. Returns True if recorded, False if already exists."""
        async with self.session() as session:
            try:
                catalyst = SeenCatalyst(
                    headline_hash=headline_hash,
                    symbol=symbol.upper(),
                    headline=headline,
                    publisher=publisher,
                )
                session.add(catalyst)
                await session.commit()
                return True
            except Exception:
                await session.rollback()
                return False

    async def is_catalyst_seen(self, headline_hash: str) -> bool:
        """Checks whether a catalyst hash has already been processed."""
        async with self.session() as session:
            result = await session.execute(
                select(SeenCatalyst.id).where(SeenCatalyst.headline_hash == headline_hash)
            )
            return result.scalar_one_or_none() is not None




def get_engine(url: str):
    return create_async_engine(url, echo=False)


def get_session_maker(engine):
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

