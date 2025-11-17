# Gen-SQL Backend (Scaffold)
A minimal, production-minded scaffold for a Gen-SQL (Generate→Ground→Regenerate) backend using FastAPI and Postgres.

This scaffold is **meant to be a starting point** — LLM calls and embeddings are mocked so you can run the service locally and replace the mocks with real providers (OpenAI, local Llama, etc.) later.

## What is included
- FastAPI service with `/health` and `/v1/query` endpoints
- Simple pseudo-schema → grounding → SQL generation pipeline (mocked LLM)
- DB executor that runs SQL against Postgres (asyncpg)
- Schema auto-refresh worker stub
- Dockerfile and docker-compose (development)
- `.env.example`

## Quickstart
1. Unzip the project and `cd` into it.
2. Create a virtualenv and install dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. Configure `.env` (copy `.env.example`) — default DB is `postgresql+asyncpg://pguser:pgpass@localhost:5432/mydb`
4. Start the app (dev):
   ```bash
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```
5. Try health: `GET http://localhost:8000/health/ready`
6. Try query (example):
   ```bash
   curl -X POST http://localhost:8000/v1/query -H 'Content-Type: application/json' -d '{"db_id":"mydb","question":"List users who placed orders above 1000"}'
   ```

## Notes
- Replace mocked LLM functions in `services/pseudo_schema.py` and `services/sql_generator.py` with real LLM calls.
- The `grounding` module uses simple string similarity; switch to embeddings easily by adding an embeddings provider and storing vectors.
