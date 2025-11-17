# workers/refresh_scheduler.py
import asyncio
import os
import json
import asyncpg
from core.config import settings

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "schemas")
os.makedirs(DATA_DIR, exist_ok=True)

INTROSPECT_TABLES_SQL = """
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public' AND table_type='BASE TABLE';
"""

INTROSPECT_COLUMNS_SQL = """
SELECT column_name
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = $1
ORDER BY ordinal_position;
"""

INTROSPECT_FKS_SQL = """
SELECT
  tc.table_name AS from_table,
  kcu.column_name AS from_column,
  ccu.table_name AS to_table,
  ccu.column_name AS to_column,
  tc.constraint_name
FROM
  information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
  ON tc.constraint_name = kcu.constraint_name AND tc.constraint_schema = kcu.constraint_schema
JOIN information_schema.constraint_column_usage AS ccu
  ON ccu.constraint_name = tc.constraint_name AND ccu.constraint_schema = tc.constraint_schema
WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = 'public';
"""

async def introspect_db(db_dsn: str):
    """Return schema dict: {tables: {table:[cols]}, relationships: [...] }"""
    conn = await asyncpg.connect(dsn=db_dsn)
    try:
        tables = {}
        rows = await conn.fetch(INTROSPECT_TABLES_SQL)
        tbl_names = [r['table_name'] for r in rows]
        for t in tbl_names:
            cols = await conn.fetch(INTROSPECT_COLUMNS_SQL, t)
            tables[t] = [c['column_name'] for c in cols]

        fk_rows = await conn.fetch(INTROSPECT_FKS_SQL)
        relationships = []
        for r in fk_rows:
            relationships.append({
                "from_table": r['from_table'],
                "from_column": r['from_column'],
                "to_table": r['to_table'],
                "to_column": r['to_column'],
                "constraint_name": r['constraint_name']
            })

        return {"tables": tables, "relationships": relationships}
    finally:
        await conn.close()

async def write_schema_file(db_id: str, schema: dict):
    path = os.path.join(DATA_DIR, f"{db_id}_schema.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2)

async def background_refresh():
    db_id = 'mydb'
    dsn = settings.DATABASE_URL
    # Try once at startup and then periodically
    try:
        schema = await introspect_db(dsn)
        await write_schema_file(db_id, schema)
    except Exception:
        # If introspect fails, we leave any existing schema in place
        pass

    while True:
        await asyncio.sleep(settings.REFRESH_INTERVAL_SECONDS)
        try:
            schema = await introspect_db(dsn)
            await write_schema_file(db_id, schema)
        except Exception:
            # failed refresh — skip until next interval
            continue
