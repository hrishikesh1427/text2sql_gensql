# services/sql_generator.py

import asyncio
import json
import re
from typing import Dict, List

from tenacity import retry, wait_exponential, stop_after_attempt

from core.config import settings
from core.llm import LLM_API_1
from core.prompts import SQL_GENERATION_SYSTEM, SQL_GENERATION_USER


# ===========================
# Internal LLM caller (sync)
# ===========================
@retry(wait=wait_exponential(min=1, max=10), stop=stop_after_attempt(3))
def _call_llm_sync(system_prompt: str, user_prompt: str, model: str):
    """
    Blocking LLM call wrapped with retry policy.
    """
    resp = LLM_API_1.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.0,
    )
    return resp


# ===========================
# Extract SQL from response
# ===========================
def _extract_sql(text: str) -> str:
    """
    Extract SQL from plain text or fenced blocks.
    """
    fenced = re.search(r"```sql\s+([\s\S]*?)```", text, re.I)
    if fenced:
        return fenced.group(1).strip()

    fenced2 = re.search(r"```([\s\S]*?)```", text)
    if fenced2:
        return fenced2.group(1).strip()

    return text.strip()


def _prompt_payload(grounded_map: Dict, relationships: List[Dict]) -> str:
    payload = {
        "tables": grounded_map,
        "relationships": relationships,
    }
    return json.dumps(payload, indent=2)


# ================================================================
# SQL GENERATION USING TABLE + COLUMN + RELATIONSHIP GROUNDING
# ================================================================
async def generate_sql(question: str, grounded_map: Dict, relationships: List[Dict]):
    grounded_json = _prompt_payload(grounded_map, relationships)

    user_prompt = SQL_GENERATION_USER.format(
        grounded=grounded_json,
        question=question,
    )

    loop = asyncio.get_running_loop()
    resp = await loop.run_in_executor(
        None,
        _call_llm_sync,
        SQL_GENERATION_SYSTEM,
        user_prompt,
        settings.SQL_GENERATION_MODEL,
    )

    content = resp.choices[0].message.content
    return _extract_sql(content)


# ================================================================
# AUTO-REPAIR SQL USING DB ERROR + COLUMN-LEVEL GROUNDING
# ================================================================
async def regenerate_sql_with_error(
    question: str,
    grounded_map: Dict,
    relationships: List[Dict],
    bad_sql: str,
    error_message: str,
) -> str:
    """
    Use the same grounded schema but add error context.
    The LLM generates a FIXED SQL.
    """

    grounded_json = _prompt_payload(grounded_map, relationships)

    correction_prompt = f"""
The previous SQL was invalid.

ERROR:
{error_message}

INVALID SQL:
{bad_sql}

Grounded schema (tables → columns → relationships):
{grounded_json}

Rules:
- Fix ONLY the SQL.
- Do NOT add or invent columns/tables.
- Use only columns listed in available_columns.
- Use only the provided relationships for JOINs.
- Use PostgreSQL interval syntax: INTERVAL '7 days'
- Return ONLY fixed SQL.
"""

    loop = asyncio.get_running_loop()
    resp = await loop.run_in_executor(
        None,
        _call_llm_sync,
        SQL_GENERATION_SYSTEM,
        correction_prompt,
        settings.SQL_GENERATION_MODEL,
    )

    content = resp.choices[0].message.content
    return _extract_sql(content)
