#!/usr/bin/env python3
"""
Diagnostic script to check database connection and list all schemas and tables.
"""

import asyncio
import asyncpg
from core.config import settings

async def check_database():
    dsn = settings.get_asyncpg_dsn()
    print("=" * 60)
    print("Database Connection Diagnostic")
    print("=" * 60)
    print(f"Connecting to: {dsn.split('@')[-1] if '@' in dsn else dsn}")
    print()
    
    try:
        conn = await asyncpg.connect(dsn=dsn)
        print("✓ Successfully connected to database!")
        print()
        
        # Check current database
        db_name = await conn.fetchval("SELECT current_database()")
        print(f"Current database: {db_name}")
        
        # List all schemas
        print("\n" + "-" * 60)
        print("Available schemas:")
        print("-" * 60)
        schemas = await conn.fetch("""
            SELECT schema_name 
            FROM information_schema.schemata 
            WHERE schema_name NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
            ORDER BY schema_name
        """)
        for row in schemas:
            print(f"  - {row['schema_name']}")
        
        # List all tables in all schemas
        print("\n" + "-" * 60)
        print("Tables in all schemas:")
        print("-" * 60)
        tables = await conn.fetch("""
            SELECT table_schema, table_name, table_type
            FROM information_schema.tables
            WHERE table_schema NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
            ORDER BY table_schema, table_name
        """)
        
        if not tables:
            print("  ⚠ No tables found in any schema!")
            print("\n  The database appears to be empty.")
            print("  Make sure you're connecting to the correct database.")
        else:
            current_schema = None
            for row in tables:
                if row['table_schema'] != current_schema:
                    current_schema = row['table_schema']
                    print(f"\n  Schema: {current_schema}")
                print(f"    - {row['table_name']} ({row['table_type']})")
        
        # Check public schema specifically
        print("\n" + "-" * 60)
        print("Tables in 'public' schema:")
        print("-" * 60)
        public_tables = await conn.fetch("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """)
        
        if not public_tables:
            print("  ⚠ No tables found in 'public' schema!")
            if tables:
                print("\n  Tables exist in other schemas. You may need to:")
                print("  1. Move tables to 'public' schema, OR")
                print("  2. Update the introspection queries to check other schemas")
        else:
            for row in public_tables:
                print(f"  - {row['table_name']}")
        
        await conn.close()
        print("\n" + "=" * 60)
        print("Diagnostic complete!")
        print("=" * 60)
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_database())

