from datetime import datetime, timezone
from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, select, func
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Mapped, declarative_base, mapped_column, relationship

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    risk_profile: Mapped[str | None] = mapped_column(String(255), nullable=True) # Stores user investment style
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



def get_engine(url: str):
    return create_async_engine(url, echo=False)


def get_session_maker(engine):
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

