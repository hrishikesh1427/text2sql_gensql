#!/usr/bin/env python3
"""
Utility script to refresh database schema and embeddings after changing DATABASE_URL.
Run this from the project root directory.

Usage:
    python refresh_db.py [--db-id mydb] [--skip-embeddings]
"""

import asyncio
import argparse
import sys
from workers.refresh_scheduler import refresh_once
from services.grounding import load_schema, regenerate_embeddings


async def main():
    parser = argparse.ArgumentParser(description="Refresh database schema and embeddings")
    parser.add_argument(
        "--db-id",
        default="mydb",
        help="Database ID to refresh (default: mydb)"
    )
    parser.add_argument(
        "--skip-embeddings",
        action="store_true",
        help="Skip regenerating embeddings (only refresh schema)"
    )
    args = parser.parse_args()

    print("=" * 60)
    print("Database Schema & Embeddings Refresh")
    print("=" * 60)
    print()

    # Step 1: Refresh schema
    print(f"Step 1: Refreshing schema for '{args.db_id}'...")
    try:
        schema = await refresh_once(args.db_id)
        print()
    except Exception as e:
        print(f"✗ Failed to refresh schema: {e}")
        sys.exit(1)

    # Step 2: Regenerate embeddings
    if not args.skip_embeddings:
        print(f"Step 2: Regenerating embeddings for '{args.db_id}'...")
        try:
            # Reload schema to ensure we have the latest
            schema = load_schema(args.db_id)
            embeddings = regenerate_embeddings(args.db_id, schema)
            
            table_count = len(embeddings.get("tables", {}))
            col_count = len(embeddings.get("columns", {}))
            print(f"✓ Embeddings regenerated successfully")
            print(f"  Generated embeddings for {table_count} tables")
            print(f"  Generated embeddings for {col_count} columns")
        except Exception as e:
            print(f"✗ Failed to regenerate embeddings: {e}")
            sys.exit(1)
    else:
        print("Step 2: Skipping embeddings regeneration (--skip-embeddings)")

    print()
    print("=" * 60)
    print("✓ Refresh complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

