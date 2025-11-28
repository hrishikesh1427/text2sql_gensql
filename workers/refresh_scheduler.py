# workers/refresh_scheduler.py
import asyncio
import os
import json
import asyncpg
from core.config import settings
from services.grounding import load_schema, regenerate_embeddings

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "schemas")
os.makedirs(DATA_DIR, exist_ok=True)

async def introspect_db(db_dsn: str):
    """Return schema dict: {tables: {table:[cols]}, relationships: [...] }"""
    conn = await asyncpg.connect(dsn=db_dsn)
    try:
        # Get list of schemas to check
        schemas_to_check = []
        if settings.DATABASE_SCHEMAS:
            # Use configured schemas
            schemas_to_check = [s.strip() for s in settings.DATABASE_SCHEMAS.split(',') if s.strip()]
        else:
            # If not configured, get all non-system schemas
            schema_rows = await conn.fetch("""
                SELECT schema_name 
                FROM information_schema.schemata 
                WHERE schema_name NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
                ORDER BY schema_name
            """)
            schemas_to_check = [r['schema_name'] for r in schema_rows]
        
        if not schemas_to_check:
            return {"tables": {}, "relationships": []}
        
        # Build SQL with schema list
        schema_placeholders = ','.join([f"${i+1}" for i in range(len(schemas_to_check))])
        
        INTROSPECT_TABLES_SQL = f"""
        SELECT table_schema, table_name
        FROM information_schema.tables
        WHERE table_schema IN ({schema_placeholders}) AND table_type='BASE TABLE'
        ORDER BY table_schema, table_name;
        """
        
        tables = {}
        rows = await conn.fetch(INTROSPECT_TABLES_SQL, *schemas_to_check)
        
        for row in rows:
            schema_name = row['table_schema']
            table_name = row['table_name']
            # Use schema.table format for table names to avoid conflicts
            full_table_name = f"{schema_name}.{table_name}" if schema_name != 'public' else table_name
            
            # Get columns for this table
            INTROSPECT_COLUMNS_SQL = """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = $1 AND table_name = $2
            ORDER BY ordinal_position;
            """
            cols = await conn.fetch(INTROSPECT_COLUMNS_SQL, row['table_schema'], table_name)
            tables[full_table_name] = [c['column_name'] for c in cols]

        # Get foreign keys from all schemas
        # Use same placeholders for both schema checks
        INTROSPECT_FKS_SQL = f"""
        SELECT
          tc.table_schema AS from_schema,
          tc.table_name AS from_table,
          kcu.column_name AS from_column,
          ccu.table_schema AS to_schema,
          ccu.table_name AS to_table,
          ccu.column_name AS to_column,
          tc.constraint_name
        FROM
          information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
          ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage AS ccu
          ON ccu.constraint_name = tc.constraint_name AND ccu.table_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY' 
          AND tc.table_schema IN ({schema_placeholders});
        """
        
        fk_rows = await conn.fetch(INTROSPECT_FKS_SQL, *schemas_to_check)
        relationships = []
        for r in fk_rows:
            from_table = f"{r['from_schema']}.{r['from_table']}" if r['from_schema'] != 'public' else r['from_table']
            to_table = f"{r['to_schema']}.{r['to_table']}" if r['to_schema'] != 'public' else r['to_table']
            relationships.append({
                "from_table": from_table,
                "from_column": r['from_column'],
                "to_table": to_table,
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
    """
    Background task that automatically refreshes schema and embeddings periodically.
    Runs once at startup, then every REFRESH_INTERVAL_SECONDS.
    """
    db_id = 'mydb'
    dsn = settings.get_asyncpg_dsn()
    last_schema_hash = None
    
    def _schema_hash(schema: dict) -> str:
        """Generate a simple hash of schema to detect changes"""
        import hashlib
        schema_str = json.dumps(schema, sort_keys=True)
        return hashlib.md5(schema_str.encode()).hexdigest()
    
    # Try once at startup and then periodically
    try:
        schema = await introspect_db(dsn)
        await write_schema_file(db_id, schema)
        # Regenerate embeddings on startup
        regenerate_embeddings(db_id, schema)
        last_schema_hash = _schema_hash(schema)
    except Exception as e:
        # If introspect fails, we leave any existing schema in place
        print(f"Warning: Initial schema refresh failed: {e}")

    while True:
        await asyncio.sleep(settings.REFRESH_INTERVAL_SECONDS)
        try:
            schema = await introspect_db(dsn)
            current_hash = _schema_hash(schema)
            
            # Only update if schema has changed
            if current_hash != last_schema_hash:
                await write_schema_file(db_id, schema)
                # Regenerate embeddings when schema changes
                regenerate_embeddings(db_id, schema)
                last_schema_hash = current_hash
        except Exception as e:
            # failed refresh — skip until next interval
            print(f"Warning: Schema refresh failed: {e}")
            continue

async def refresh_once(db_id: str = 'mydb'):
    """Run a single schema refresh (useful for manual updates)"""
    dsn = settings.get_asyncpg_dsn()
    try:
        print(f"Connecting to database: {dsn.split('@')[-1] if '@' in dsn else dsn}")
        schema = await introspect_db(dsn)
        await write_schema_file(db_id, schema)
        print(f"✓ Schema refreshed successfully for '{db_id}'")
        print(f"  Found {len(schema.get('tables', {}))} tables")
        print(f"  Found {len(schema.get('relationships', []))} relationships")
        return schema
    except Exception as e:
        print(f"✗ Failed to refresh schema: {e}")
        raise

if __name__ == "__main__":
    # Allow running this script directly to refresh schema once
    asyncio.run(refresh_once())
