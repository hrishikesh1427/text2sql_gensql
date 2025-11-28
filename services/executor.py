import asyncio
import asyncpg
import re
from typing import Dict, Set

from core.config import settings

_pool = None
_column_types_cache: Dict[str, Dict[str, str]] | None = None
_textual_column_index: Dict[str, Set[str]] | None = None
_column_lock = asyncio.Lock()

TEXTUAL_TYPES = {"character varying", "text", "varchar", "bpchar", "uuid", "citext"}
TABLE_ALIAS_RE = re.compile(
    r"\b(from|join)\s+([a-zA-Z_][\w\.]*)(?:\s+(?:as\s+)?([a-zA-Z_][\w]*))?",
    re.IGNORECASE,
)
EQUALITY_RE = re.compile(
    r"(?P<left>(?:[a-zA-Z_][\w]*\.){0,2}\"?[a-zA-Z_][\w]*\"?)\s*=\s*(?P<literal>-?\d+)(?![\d\.])",
    re.IGNORECASE,
)
EQUALITY_RE_REVERSED = re.compile(
    r"(?P<literal>-?\d+)\s*=\s*(?P<right>(?:[a-zA-Z_][\w]*\.){0,2}\"?[a-zA-Z_][\w]*\"?)",
    re.IGNORECASE,
)
IN_RE = re.compile(
    r"(?P<col>(?:[a-zA-Z_][\w]*\.){0,2}\"?[a-zA-Z_][\w]*\"?)\s+IN\s*\((?P<values>[^)]+)\)",
    re.IGNORECASE,
)


def _normalize_identifier(token: str) -> str:
    return token.strip().strip('"').lower()


async def _get_pool():
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(dsn=settings.get_asyncpg_dsn(), min_size=1, max_size=5)
    return _pool


async def _ensure_column_metadata():
    """
    Introspect information_schema once and cache column data types so that we can
    patch obvious literal type mismatches before touching the database.
    """
    global _column_types_cache, _textual_column_index
    if _column_types_cache is not None and _textual_column_index is not None:
        return

    async with _column_lock:
        if _column_types_cache is not None and _textual_column_index is not None:
            return

        pool = await _get_pool()
        async with pool.acquire() as conn:
            schemas = [s.strip() for s in settings.DATABASE_SCHEMAS.split(",") if s.strip()]
            base_query = """
                SELECT table_schema || '.' || table_name AS full_table,
                       column_name,
                       data_type
                FROM information_schema.columns
                WHERE table_schema NOT IN ('information_schema','pg_catalog')
            """
            params = []
            if schemas:
                base_query += " AND table_schema = ANY($1::text[])"
                params.append(schemas)
            rows = await conn.fetch(base_query, *params)

        column_map: Dict[str, Dict[str, str]] = {}
        text_index: Dict[str, Set[str]] = {}

        for row in rows:
            table = _normalize_identifier(row["full_table"])
            column = _normalize_identifier(row["column_name"])
            data_type = _normalize_identifier(row["data_type"])
            table_entry = column_map.setdefault(table, {})
            table_entry[column] = data_type
            if data_type in TEXTUAL_TYPES:
                text_index.setdefault(column, set()).add(table)

        _column_types_cache = column_map
        _textual_column_index = text_index


def _build_alias_map(sql: str) -> Dict[str, str]:
    """
    Map aliases → fully-qualified table names (schema.table).
    """
    alias_map: Dict[str, str] = {}
    for _, table, alias in TABLE_ALIAS_RE.findall(sql):
        table_norm = _normalize_identifier(table)
        alias_map[table_norm] = table_norm
        if "." in table_norm:
            alias_map[table_norm.split(".")[-1]] = table_norm
        if alias:
            alias_map[_normalize_identifier(alias)] = table_norm
    return alias_map


def _should_quote(owner: str | None, column: str, alias_map: Dict[str, str]) -> bool:
    """
    Decide whether the literal next to this column should be treated as text.
    """
    if _column_types_cache is None or _textual_column_index is None:
        return False

    if owner:
        table_key = alias_map.get(owner, owner)
        if table_key and table_key in _column_types_cache:
            data_type = _column_types_cache[table_key].get(column)
            return data_type in TEXTUAL_TYPES

    candidate_tables = _textual_column_index.get(column, set())
    if len(candidate_tables) == 1:
        table_key = next(iter(candidate_tables))
        data_type = _column_types_cache.get(table_key, {}).get(column)
        return data_type in TEXTUAL_TYPES
    return False


def _quote_literal(literal: str) -> str:
    return f"'{literal}'"


def _extract_owner_and_column(identifier: str) -> tuple[str | None, str]:
    parts = [segment for segment in identifier.split(".") if segment]
    if not parts:
        return None, ""
    column = _normalize_identifier(parts[-1])
    owner = _normalize_identifier(".".join(parts[:-1])) if len(parts) > 1 else None
    return owner, column


def _quote_numeric_literals(sql: str) -> str:
    """
    Quote bare numeric literals when they are compared against columns that are
    stored as text/varchar to avoid operator mismatch errors.
    """
    if _column_types_cache is None or _textual_column_index is None:
        return sql

    alias_map = _build_alias_map(sql)

    def handle_equality(match, left_key: str, literal_key: str, right_side: bool = False):
        identifier = match.group(left_key)
        literal = match.group(literal_key)
        owner, column = _extract_owner_and_column(identifier)
        if _should_quote(owner, column, alias_map):
            quoted = _quote_literal(literal)
            if right_side:
                return f"{quoted} = {identifier}"
            return f"{identifier} = {quoted}"
        return match.group(0)

    sql = EQUALITY_RE.sub(lambda m: handle_equality(m, "left", "literal"), sql)
    sql = EQUALITY_RE_REVERSED.sub(lambda m: handle_equality(m, "right", "literal", right_side=True), sql)

    def handle_in_clause(match):
        identifier = match.group("col")
        owner, column = _extract_owner_and_column(identifier)
        if not _should_quote(owner, column, alias_map):
            return match.group(0)
        values = match.group("values")
        if "select" in values.lower():
            return match.group(0)
        parts = [p.strip() for p in values.split(",")]
        new_parts = []
        for part in parts:
            if re.fullmatch(r"-?\d+", part) and not part.startswith("'"):
                new_parts.append(_quote_literal(part))
            else:
                new_parts.append(part)
        return f"{identifier} IN ({', '.join(new_parts)})"

    sql = IN_RE.sub(handle_in_clause, sql)
    return sql


async def execute_sql(sql: str, db_id: str, enforce_limit: bool = True):
    # enforce small LIMIT if missing
    if enforce_limit and sql.strip().lower().startswith("select") and "limit" not in sql.lower():
        sql = sql.rstrip(";") + f" LIMIT {settings.MAX_ROWS};"

    await _ensure_column_metadata()
    sql = _quote_numeric_literals(sql)

    pool = await _get_pool()
    async with pool.acquire() as conn:
        # set a statement timeout per session (ms)
        try:
            await conn.execute("SET LOCAL statement_timeout = 60000;")  # 60s
            rows = await conn.fetch(sql)
            return [dict(r) for r in rows]
        except Exception as e:
            raise
