import asyncpg, asyncio
from core.config import settings

_pool = None

async def _get_pool():
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(dsn=settings.get_asyncpg_dsn(), min_size=1, max_size=5)
    return _pool

async def execute_sql(sql: str, db_id: str):
    # enforce small LIMIT if missing
    if sql.strip().lower().startswith('select') and 'limit' not in sql.lower():
        sql = sql.rstrip(';') + f' LIMIT {settings.MAX_ROWS};'
    pool = await _get_pool()
    async with pool.acquire() as conn:
        # set a statement timeout per session (ms)
        try:
            await conn.execute("SET LOCAL statement_timeout = 60000;")  # 60s
            rows = await conn.fetch(sql)
            return [dict(r) for r in rows]
        except Exception as e:
            raise
