import asyncio
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

SQLITE_URL = "sqlite+aiosqlite:///dca_catcher.db"
PG_URL = "postgresql+asyncpg://postgres:0656781986Get*@db.ipgblreytvsgzdtrjuom.supabase.co:5432/postgres"

TABLES = [
    "users",
    "watchlists",
    "signals",
    "user_analysis_memories",
    "seen_catalysts"
]

def parse_date(date_str):
    if not date_str:
        return None
    try:
        if "." in date_str:
            return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S.%f")
        return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None

async def migrate():
    print("Starting migration from SQLite to Postgres...")
    sqlite_engine = create_async_engine(SQLITE_URL)
    pg_engine = create_async_engine(PG_URL, echo=False)

    async with sqlite_engine.connect() as sqlite_conn:
        for table_name in TABLES:
            print(f"Migrating table: {table_name}")
            try:
                result = await sqlite_conn.execute(text(f"SELECT * FROM {table_name}"))
                rows = result.mappings().all()
                
                if not rows:
                    print(f"  -> Table {table_name} is empty, skipping.")
                    continue

                success_count = 0
                for row in rows:
                    columns = ", ".join(row.keys())
                    placeholders = ", ".join([f":{k}" for k in row.keys()])
                    simple_insert = text(f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})")
                    
                    params = dict(row)
                    
                    # Fix data types
                    for col in ["created_at", "analyzed_at", "seen_at"]:
                        if col in params and isinstance(params[col], str):
                            params[col] = parse_date(params[col])
                            
                    if "notify_dm" in params:
                        params["notify_dm"] = bool(params["notify_dm"])
                        
                    try:
                        async with pg_engine.begin() as pg_conn:
                            await pg_conn.execute(simple_insert, params)
                        success_count += 1
                    except IntegrityError:
                        pass
                    except Exception as e:
                        print(f"  -> Row error in {table_name}: {e}")

                try:
                    async with pg_engine.begin() as pg_conn:
                        seq_sql = text(f"SELECT setval('{table_name}_id_seq', (SELECT MAX(id) FROM {table_name}));")
                        await pg_conn.execute(seq_sql)
                except Exception:
                    pass

                print(f"  -> Migrated {success_count}/{len(rows)} rows successfully.")
            except Exception as e:
                print(f"  -> Error migrating table {table_name}: {e}")

    await sqlite_engine.dispose()
    await pg_engine.dispose()
    print("Migration completed!")

if __name__ == "__main__":
    asyncio.run(migrate())
