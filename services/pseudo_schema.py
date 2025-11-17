import asyncio
import json
import re
from tenacity import retry, wait_exponential, stop_after_attempt
from core.llm import LLM_API_1
from core.prompts import PSEUDO_SCHEMA_SYSTEM, PSEUDO_SCHEMA_USER

@retry(wait=wait_exponential(min=1, max=10), stop=stop_after_attempt(3))
def _call_llm_sync(user_prompt: str, model: str):
    resp = LLM_API_1.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": PSEUDO_SCHEMA_SYSTEM},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.0,
    )
    return resp

async def generate_pseudo_schema(question: str, table_hints=None) -> list:
    tables_txt = ", ".join(table_hints) if table_hints else "None"
    user_prompt = PSEUDO_SCHEMA_USER.format(
        tables=tables_txt,
        question=question
    )

    loop = asyncio.get_running_loop()
    resp = await loop.run_in_executor(
        None, _call_llm_sync, user_prompt, "gpt-4o-mini"
    )

    content = resp.choices[0].message.content

    m = re.search(r"(\[.*\])", content, re.S)
    json_text = m.group(1) if m else content

    try:
        return json.loads(json_text)
    except:
        return []
