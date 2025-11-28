# main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import asyncio
from core.config import settings
from services import pseudo_schema, grounding, sql_generator, validator, executor
from workers import refresh_scheduler

app = FastAPI(title="Gen-SQL Backend (Real LLMs)")

@app.on_event("startup")
async def startup():
    # start schema refresh worker in background
    asyncio.create_task(refresh_scheduler.background_refresh())

@app.get("/health/ready")
async def health_ready():
    return {"status":"ready"}

class QueryRequest(BaseModel):
    db_id: str
    question: str

class QueryResponse(BaseModel):
    sql: str | None = None
    results: list | None = None
    error: str | None = None

@app.post("/v1/query", response_model=QueryResponse)
async def query(req: QueryRequest):
    print(">>> /v1/query request received", req.model_dump())

    # 1. Load stored schema to provide table hints to pseudo-schema LLM
    schema = grounding.load_schema(req.db_id)
    print("Loaded schema for", req.db_id, "with tables:", list(schema.get("tables", {}).keys()))
    table_hints = list(schema.get("tables", {}).keys()) if schema and schema.get("tables") else None

    # 2. Generate pseudo-schema (LLM)
    pseudo = await pseudo_schema.generate_pseudo_schema(req.question, table_hints)
    print("Generated pseudo schema:", pseudo)

    # 3. Ground pseudo-schema to real schema (returns mapping + relationships)
    grounded_map, relationships = await grounding.ground(pseudo, req.db_id)
    print("Grounded schema. Relationships count:", len(relationships))

    # 4. Generate SQL (LLM) using grounded_map + relationships
    sql = await sql_generator.generate_sql(req.question, grounded_map, relationships)
    sql = (sql or "").strip()
    print("Generated SQL:", sql)

    # 5. Validate SQL (pass relationships separately)
    ok, msg, repaired_sql = validator.validate_sql(sql, grounded_map, relationships)
    print("Validation result:", ok, msg)

    if not ok:
        # AUTO-REPAIR USING LLM (pass relationships)
        print("Validation failed, regenerating SQL with error")
        repaired_sql = await sql_generator.regenerate_sql_with_error(
            question=req.question,
            grounded_map=grounded_map,
            relationships=relationships,
            bad_sql=sql,
            error_message=msg
        )

        # validate repaired SQL
        ok2, msg2, repaired2 = validator.validate_sql(repaired_sql, grounded_map, relationships)
        print("Second validation result:", ok2, msg2)
        if not ok2:
            return {
                "sql": repaired_sql,
                "results": None,
                "error": msg2
            }

        final_sql = repaired_sql
    else:
        final_sql = repaired_sql or sql

    # 6. Execute SQL with automatic recovery attempt on runtime error
    try:
        print("Executing SQL:", final_sql)
        rows = await executor.execute_sql(final_sql, req.db_id)
        print("SQL executed, rows returned:", len(rows) if rows else 0)
    except Exception as e:
        # Attempt to auto-repair based on database error feedback
        print("Execution failed, attempting auto-repair:", e)
        repair_sql = await sql_generator.regenerate_sql_with_error(
            question=req.question,
            grounded_map=grounded_map,
            relationships=relationships,
            bad_sql=final_sql,
            error_message=str(e),
        )
        ok3, msg3, repaired3 = validator.validate_sql(repair_sql, grounded_map, relationships)
        print("Repair validation result:", ok3, msg3)
        if not ok3:
            raise HTTPException(
                status_code=400,
                detail=f"{str(e)} | Auto-repair failed validation: {msg3}",
            )
        repair_final_sql = repaired3 or repair_sql
        try:
            print("Executing repaired SQL")
            rows = await executor.execute_sql(repair_final_sql, req.db_id)
            final_sql = repair_final_sql
            print("Repair execution succeeded")
        except Exception as e2:
            raise HTTPException(
                status_code=500,
                detail=f"{str(e)} | Repair attempt failed: {str(e2)}",
            )
    response = {"sql": final_sql, "results": rows, "error": None}
    print("Returning response")
    return response
