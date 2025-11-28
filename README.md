# Gen-SQL Backend

A production-ready Gen-SQL (Generate→Ground→Regenerate) backend using FastAPI and PostgreSQL. This backend automatically converts natural language questions into SQL queries and executes them against your database.

## Features

- 🤖 **Natural Language to SQL**: Convert questions to SQL queries using LLMs
- 🔄 **Automatic Schema Refresh**: Background worker automatically keeps database schema up-to-date
- 📊 **Multi-Schema Support**: Works with databases containing multiple schemas
- 🔍 **Semantic Grounding**: Uses embeddings for intelligent table and column matching
- ⚡ **Auto-Repair**: Automatically fixes SQL errors using LLM feedback
- 🚀 **Fully Automated**: No manual intervention needed - everything runs in the background

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Project](#running-the-project)
- [Testing with Postman](#testing-with-postman)
- [Project Structure](#project-structure)
- [Troubleshooting](#troubleshooting)
- [API Documentation](#api-documentation)

---

## Prerequisites

Before you begin, ensure you have the following installed:

- **Python 3.11+** - [Download Python](https://www.python.org/downloads/)
- **PostgreSQL** - [Download PostgreSQL](https://www.postgresql.org/download/)
- **Git** - [Download Git](https://git-scm.com/downloads)
- **Postman** (optional, for API testing) - [Download Postman](https://www.postman.com/downloads/)

---

## Installation

### Step 1: Clone the Repository

```bash
git clone <your-repository-url>
cd gen_sql_backend
```

### Step 2: Create Virtual Environment

**Windows:**
```bash
python -m venv .venv
.venv\Scripts\activate
```

**Linux/Mac:**
```bash
python -m venv .venv
source .venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

This will install all required packages including:
- FastAPI (web framework)
- asyncpg (PostgreSQL async driver)
- sentence-transformers (embeddings)
- OpenAI (LLM integration)
- And more...

### Step 4: Verify Installation

```bash
python --version  # Should show Python 3.11+
pip list  # Should show all installed packages
```

---

## Configuration

### Step 1: Create `.env` File

Create a `.env` file in the project root directory:

```bash
# Windows
copy .env.example .env

# Linux/Mac
cp .env.example .env
```

**Important:** The `.env` file is required and contains sensitive credentials. It should **never** be committed to Git (it's already in `.gitignore`).

### Step 2: Configure Database Connection

Edit the `.env` file with your database credentials:

```env
# Database Configuration
# REQUIRED: Set your database connection string
DATABASE_URL=postgresql+asyncpg://USERNAME:PASSWORD@HOST:PORT/DATABASE

# Example:
# DATABASE_URL=postgresql+asyncpg://postgres:your_password@localhost:5432/your_database

# Optional: Specify which schemas to monitor (comma-separated)
# Leave empty to auto-detect all non-system schemas
DATABASE_SCHEMAS=public,chatbot

# Refresh interval in seconds (default: 300 = 5 minutes)
REFRESH_INTERVAL_SECONDS=300

# Maximum rows to return per query
MAX_ROWS=1000

# LLM Configuration
OPENAI_API_KEY=your_openai_api_key_here
PSEUDO_SCHEMA_MODEL=gpt-4o-mini
SQL_GENERATION_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-large
TOP_K_GROUND=5
```

**Important Notes:**
- Replace `USERNAME`, `PASSWORD`, `HOST`, `PORT`, and `DATABASE` with your actual database credentials
- The `DATABASE_URL` format supports both `postgresql+asyncpg://` and `postgresql://`
- If your tables are in multiple schemas, list them in `DATABASE_SCHEMAS`

### Step 3: Verify Database Connection

Test your database connection:

```bash
python check_db.py
```

This will:
- Test the database connection
- List all available schemas
- Show all tables in your database
- Help identify any connection issues

**Expected Output:**
```
============================================================
Database Connection Diagnostic
============================================================
Connecting to: localhost:5432/slingobot

✓ Successfully connected to database!

Current database: slingobot

------------------------------------------------------------
Available schemas:
------------------------------------------------------------
  - chatbot
  - public

------------------------------------------------------------
Tables in all schemas:
------------------------------------------------------------
  Schema: chatbot
    - call_data (BASE TABLE)
...
```

---

## Running the Project

### Step 1: Refresh Database Schema and Embeddings

Before starting the server, refresh your database schema:

```bash
python refresh_db.py
```

This will:
- Connect to your database
- Introspect all tables, columns, and relationships
- Save schema to `data/schemas/mydb_schema.json`
- Generate embeddings for semantic search
- Save embeddings to `data/embeddings/mydb_embeddings.json`

**Expected Output:**
```
============================================================
Database Schema & Embeddings Refresh
============================================================

Step 1: Refreshing schema for 'mydb'...
Connecting to database: localhost:5432/slingobot
✓ Schema refreshed successfully for 'mydb'
  Found 1 tables
  Found 0 relationships

Step 2: Regenerating embeddings for 'mydb'...
✓ Embeddings regenerated successfully
  Generated embeddings for 1 tables
  Generated embeddings for 37 columns

============================================================
✓ Refresh complete!
============================================================
```

**Note:** This step is only needed:
- On initial setup
- After changing `DATABASE_URL`
- When you want to force an immediate refresh

The server will automatically refresh the schema every 5 minutes (configurable via `REFRESH_INTERVAL_SECONDS`).

### Step 2: Start the Server

**Development Mode (with auto-reload):**
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Production Mode:**
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

**Expected Output:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

### Step 3: Verify Server is Running

Open your browser or use curl:

```bash
curl http://localhost:8000/health/ready
```

**Expected Response:**
```json
{"status":"ready"}
```

Or visit: `http://localhost:8000/docs` for interactive API documentation.

---

## Testing with Postman

### Step 1: Install Postman

Download and install Postman from [postman.com](https://www.postman.com/downloads/)

### Step 2: Create a New Collection

1. Open Postman
2. Click **"New"** → **"Collection"**
3. Name it: **"Gen-SQL Backend API"**

### Step 3: Test Health Check Endpoint

1. Click **"Add Request"** in your collection
2. Name it: **"Health Check"**
3. Set method to: **GET**
4. Enter URL: `http://localhost:8000/health/ready`
5. Click **"Send"**

**Expected Response:**
```json
{
  "status": "ready"
}
```

### Step 4: Test Query Endpoint

1. Click **"Add Request"** in your collection
2. Name it: **"Query Database"**
3. Set method to: **POST**
4. Enter URL: `http://localhost:8000/v1/query`

#### Configure Headers:

1. Go to **"Headers"** tab
2. Add header:
   - **Key:** `Content-Type`
   - **Value:** `application/json`

#### Configure Body:

1. Go to **"Body"** tab
2. Select **"raw"**
3. Select **"JSON"** from dropdown
4. Enter request body:

```json
{
  "db_id": "mydb",
  "question": "Show me all call data"
}
```

5. Click **"Send"**

**Expected Response:**
```json
{
  "sql": "SELECT * FROM chatbot.call_data LIMIT 1000;",
  "results": [
    {
      "id": 1,
      "call_id": "CALL001",
      "filename": "call_001.wav",
      "date": "2024-01-01",
      ...
    }
  ],
  "error": null
}
```

### Step 5: Example Queries

Try these example queries (replace the `question` field in the request body):

#### Example 1: List All Records
```json
{
  "db_id": "mydb",
  "question": "List all call data"
}
```

#### Example 2: Filter by Agent
```json
{
  "db_id": "mydb",
  "question": "Show me calls handled by agent John"
}
```

#### Example 3: Aggregate Data
```json
{
  "db_id": "mydb",
  "question": "What is the average call score?"
}
```

#### Example 4: Count Records
```json
{
  "db_id": "mydb",
  "question": "How many calls are there in total?"
}
```

#### Example 5: Filter by Score
```json
{
  "db_id": "mydb",
  "question": "Show me calls with score above 80"
}
```

#### Example 6: Date Range Query
```json
{
  "db_id": "mydb",
  "question": "Get all calls from today"
}
```

### Step 6: Set Up Environment Variables (Optional)

For easier testing, create a Postman Environment:

1. Click **"Environments"** → **"+"**
2. Name it: **"Local Development"**
3. Add variables:
   - `base_url`: `http://localhost:8000`
   - `db_id`: `mydb`
4. Use in requests:
   - URL: `{{base_url}}/v1/query`
   - Body: `{"db_id": "{{db_id}}", "question": "..."}`

---

## Project Structure

```
gen_sql_backend/
├── core/                    # Core configuration and utilities
│   ├── config.py           # Settings and configuration
│   ├── llm.py              # LLM integration
│   └── logger.py           # Logging configuration
├── services/                # Business logic services
│   ├── executor.py         # SQL execution
│   ├── grounding.py        # Schema grounding with embeddings
│   ├── pseudo_schema.py    # Pseudo-schema generation
│   ├── sql_generator.py    # SQL generation
│   └── validator.py        # SQL validation
├── workers/                 # Background workers
│   └── refresh_scheduler.py # Schema refresh worker
├── data/                    # Generated data files
│   ├── schemas/            # Database schema JSON files
│   └── embeddings/         # Embedding cache files
├── main.py                  # FastAPI application entry point
├── refresh_db.py           # Manual schema refresh utility
├── check_db.py             # Database diagnostic tool
├── requirements.txt        # Python dependencies
├── .env                    # Environment variables (create this)
└── README.md               # This file
```

---

## Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'X'"

**Solution:**
```bash
# Make sure virtual environment is activated
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# Reinstall dependencies
pip install -r requirements.txt
```

### Issue: "password authentication failed"

**Solution:**
1. Check your `.env` file has correct `DATABASE_URL`
2. Verify database credentials are correct
3. Ensure PostgreSQL is running
4. Test connection: `python check_db.py`

### Issue: "Found 0 tables" when running refresh_db.py

**Solution:**
1. Run `python check_db.py` to see which schemas have tables
2. Update `DATABASE_SCHEMAS` in `.env` to include the correct schemas
3. Example: `DATABASE_SCHEMAS=public,chatbot,your_schema`

### Issue: "invalid DSN: scheme is expected to be either 'postgresql' or 'postgres'"

**Solution:**
- This is automatically handled by the code
- Make sure you're using the latest version
- The `get_asyncpg_dsn()` method converts the URL automatically

### Issue: Server won't start

**Solution:**
1. Check if port 8000 is already in use
2. Try a different port: `uvicorn main:app --port 8001`
3. Check for errors in terminal output
4. Verify all dependencies are installed

### Issue: API returns empty results

**Solution:**
1. Verify database has data: `python check_db.py`
2. Check if schema was refreshed: `python refresh_db.py`
3. Verify the generated SQL in the response
4. Check database connection is working

### Issue: Embeddings not generating

**Solution:**
1. First time: embeddings are generated automatically
2. Force regenerate: `python refresh_db.py`
3. Check `data/embeddings/` directory exists
4. Verify sentence-transformers is installed

---

## API Documentation

### Health Check

**Endpoint:** `GET /health/ready`

**Response:**
```json
{
  "status": "ready"
}
```

### Query Database

**Endpoint:** `POST /v1/query`

**Request Body:**
```json
{
  "db_id": "mydb",
  "question": "Your natural language question here"
}
```

**Response:**
```json
{
  "sql": "SELECT * FROM table_name LIMIT 1000;",
  "results": [
    {
      "column1": "value1",
      "column2": "value2"
    }
  ],
  "error": null
}
```

**Error Response:**
```json
{
  "sql": "SELECT * FROM invalid_table;",
  "results": null,
  "error": "Error message here"
}
```

### Interactive API Docs

Visit `http://localhost:8000/docs` for Swagger UI documentation.

---

## Automation Features

The backend is **fully automated**:

- ✅ **Automatic Schema Refresh**: Runs every 5 minutes (configurable)
- ✅ **Automatic Embedding Regeneration**: Updates when schema changes
- ✅ **Background Worker**: Starts automatically with the server
- ✅ **No Manual Intervention**: Everything runs in the background

You only need to run `refresh_db.py` manually when:
- Initial setup
- Changing database URL
- Forcing immediate refresh (optional)

---

## Additional Resources

- **Postman Testing Guide**: See `POSTMAN_TESTING_GUIDE.md` for detailed Postman instructions
- **Commit Messages**: See `COMMIT_MESSAGE_1.md` and `COMMIT_MESSAGE_2.md` for change history
- **Git Instructions**: See `GIT_COMMIT_INSTRUCTIONS.md` for version control

---

## Support

For issues or questions:
1. Check the [Troubleshooting](#troubleshooting) section
2. Review server logs in terminal
3. Run diagnostic tools: `python check_db.py`
4. Check database connection and schema

---

## License

[Your License Here]

---

**Happy Querying! 🚀**
