# services/grounding.py

import os
import json
import numpy as np
from sentence_transformers import SentenceTransformer

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
SCHEMA_DIR = os.path.join(DATA_DIR, "schemas")
EMB_DIR = os.path.join(DATA_DIR, "embeddings")

os.makedirs(EMB_DIR, exist_ok=True)

_model = SentenceTransformer("all-MiniLM-L6-v2")


# ------------------------
# Load schema & emb cache
# ------------------------

def load_schema(db_id: str):
    """
    Public: load stored schema JSON for given db_id.
    Returns dict with keys: "tables", "relationships"
    """
    path = os.path.join(SCHEMA_DIR, f"{db_id}_schema.json")
    if not os.path.exists(path):
        # return minimal fallback to avoid crash; caller should handle real schema presence
        return {"tables": {}, "relationships": []}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _emb_path(db_id: str):
    return os.path.join(EMB_DIR, f"{db_id}_embeddings.json")


def _compute_embedding(text: str):
    return _model.encode([text], convert_to_numpy=True)[0].tolist()


def _compute_bulk(texts: list):
    return _model.encode(texts, convert_to_numpy=True).tolist()


def _load_or_create_embeddings(db_id: str, schema: dict):
    emb_file = _emb_path(db_id)

    # Load cache
    if os.path.exists(emb_file):
        with open(emb_file, "r", encoding="utf-8") as f:
            return json.load(f)

    # Build cache
    tables = list(schema.get("tables", {}).keys())
    table_vecs = _compute_bulk(tables) if tables else []

    col_keys = []
    for t, cols in schema.get("tables", {}).items():
        for c in cols:
            col_keys.append(f"{t}.{c}")

    col_vecs = _compute_bulk(col_keys) if col_keys else []

    store = {
        "tables": {t: table_vecs[i] for i, t in enumerate(tables)} if tables else {},
        "columns": {col_keys[i]: col_vecs[i] for i in range(len(col_keys))} if col_keys else {}
    }

    with open(emb_file, "w", encoding="utf-8") as f:
        json.dump(store, f, indent=2)

    return store


def regenerate_embeddings(db_id: str, schema: dict = None):
    """
    Force regenerate embeddings for a given db_id.
    If schema is not provided, it will be loaded from the schema file.
    """
    if schema is None:
        schema = load_schema(db_id)
    
    emb_file = _emb_path(db_id)
    
    # Build cache (force regenerate)
    tables = list(schema.get("tables", {}).keys())
    table_vecs = _compute_bulk(tables) if tables else []

    col_keys = []
    for t, cols in schema.get("tables", {}).items():
        for c in cols:
            col_keys.append(f"{t}.{c}")

    col_vecs = _compute_bulk(col_keys) if col_keys else []

    store = {
        "tables": {t: table_vecs[i] for i, t in enumerate(tables)} if tables else {},
        "columns": {col_keys[i]: col_vecs[i] for i in range(len(col_keys))} if col_keys else {}
    }

    with open(emb_file, "w", encoding="utf-8") as f:
        json.dump(store, f, indent=2)

    return store


# ------------------------
# Cosine similarity
# ------------------------

def _cos(a, b):
    a = np.array(a)
    b = np.array(b)
    if np.linalg.norm(a) == 0 or np.linalg.norm(b) == 0:
        return 0.0
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


# ------------------------
# Column + table grounding
# ------------------------

async def ground(pseudo_schema: list, db_id: str):
    """
    Returns:
      final_map: {
          pseudo_table_name: {
              "matched_table": real_table_name,
              "available_columns": [...],
              "column_mapping": { pseudo_col: real_col, ... },
              "requested_columns": [...]
          },
          ...
      }
      relationships: [ {from_table, from_column, to_table, to_column}, ... ]
    """
    schema = load_schema(db_id)
    emb_cache = _load_or_create_embeddings(db_id, schema)

    real_tables = list(schema.get("tables", {}).keys())
    table_embs = emb_cache.get("tables", {})
    col_embs = emb_cache.get("columns", {})

    final_map = {}

    for entry in pseudo_schema:
        pseudo_table = entry.get("table")
        pseudo_cols = entry.get("cols", []) or []

        # ------------ TABLE GROUNDING -------------
        p_vec = _compute_embedding(pseudo_table)

        best_table = None
        best_score = -1.0

        for t in real_tables:
            tv = table_embs.get(t)
            if tv is None:
                continue
            score = _cos(p_vec, tv)
            if score > best_score:
                best_score = score
                best_table = t

        # fallback: pick first real table if nothing matched
        if best_table is None and real_tables:
            best_table = real_tables[0]

        real_cols = schema.get("tables", {}).get(best_table, [])

        # ------------ COLUMN GROUNDING -------------
        column_mapping = {}
        requested_cols = set()

        for pc in pseudo_cols:
            p_col_vec = _compute_embedding(pc)
            best_col = None
            best_col_score = -1.0

            for rc in real_cols:
                rc_key = f"{best_table}.{rc}"
                vec = col_embs.get(rc_key)
                if vec is None:
                    continue
                score = _cos(p_col_vec, vec)
                if score > best_col_score:
                    best_col_score = score
                    best_col = rc

            if best_col is None and real_cols:
                best_col = real_cols[0]

            column_mapping[pc] = best_col
            requested_cols.add(best_col)

        final_map[pseudo_table] = {
            "matched_table": best_table,
            "available_columns": real_cols,
            "column_mapping": column_mapping,
            "requested_columns": list(requested_cols)
        }

    # Return mapping + global relationship list
    relationships = schema.get("relationships", []) if schema else []
    return final_map, relationships
