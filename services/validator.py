# services/validator.py
import re

FORBIDDEN = ["drop", "delete", "update", "insert", "alter", "truncate"]


def validate_sql(sql: str, grounded_map: dict, relationships: list):
    """
    Validates SQL using:
      - grounded_map: mapping produced by grounding.ground (per-table entries with available_columns)
      - relationships: global list of FK relationships
    Returns: (ok:bool, message:str, repaired_sql_or_none)
    """
    low = sql.lower()

    for word in FORBIDDEN:
        if re.search(rf"\b{word}\b", low):
            return False, "Destructive SQL not allowed", None

    # Build reference maps
    table_cols = {}   # table_name -> set(columns)
    all_cols = set()  # "table.col" strings lowercase
    fk_set = set()    # tuples (from_table, from_col, to_table, to_col) lowercase

    # Collect table columns from grounded_map
    for p_table, entry in grounded_map.items():
        table = entry.get("matched_table")
        cols = entry.get("available_columns", []) or []
        if table:
            table_cols[table.lower()] = {c.lower() for c in cols}
            for c in cols:
                all_cols.add(f"{table}.{c}".lower())

    # Collect relationships from provided relationships list
    for rel in (relationships or []):
        f_tbl = rel.get("from_table")
        f_col = rel.get("from_column")
        t_tbl = rel.get("to_table")
        t_col = rel.get("to_column")
        if f_tbl and f_col and t_tbl and t_col:
            fk_set.add((f_tbl.lower(), f_col.lower(), t_tbl.lower(), t_col.lower()))
            fk_set.add((t_tbl.lower(), t_col.lower(), f_tbl.lower(), f_col.lower()))

    # -----------------------------------------------------
    # Validate qualified column references: table.col or alias.col
    # -----------------------------------------------------
    # Extract qualified references
    for tbl, col in re.findall(r"([a-zA-Z_][\w]*)\.([a-zA-Z_][\w]*)", sql):
        tbl_low = tbl.lower()
        col_low = col.lower()
        # If table exists in table_cols, validate col
        if tbl_low in table_cols:
            if col_low not in table_cols[tbl_low]:
                return False, f"Column '{col}' not found in table '{tbl}'", None
        # else: tbl might be alias; skip strict validation here

    # -----------------------------------------------------
    # Validate JOIN ON conditions are FK pairs
    # -----------------------------------------------------
    # Find ON clauses (heuristic)
    on_pairs = re.findall(
        r"on\s+([a-zA-Z_][\w]*)\.([a-zA-Z_][\w]*)\s*=\s*([a-zA-Z_][\w]*)\.([a-zA-Z_][\w]*)",
        sql,
        flags=re.I,
    )

    for l_tbl, l_col, r_tbl, r_col in on_pairs:
        l_tbl_low = l_tbl.lower()
        r_tbl_low = r_tbl.lower()
        l_col_low = l_col.lower()
        r_col_low = r_col.lower()

        # If either side is an alias not present in table_cols, we try to be permissive
        # but if real table names appear, strictly validate FK presence
        pair = (l_tbl_low, l_col_low, r_tbl_low, r_col_low)
        pair_rev = (r_tbl_low, r_col_low, l_tbl_low, l_col_low)

        if pair not in fk_set and pair_rev not in fk_set:
            # If left or right table matches one of the grounded matched_table names, then this is invalid
            left_known = l_tbl_low in table_cols
            right_known = r_tbl_low in table_cols
            if left_known or right_known:
                return False, f"Invalid join: {l_tbl}.{l_col} ↔ {r_tbl}.{r_col}", None
            # otherwise be permissive (alias-heavy SQL) and skip strict failure

    return True, "ok", None
