# Postman Testing Guide

## Step 1: Start the Server

First, make sure your server is running:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The server will be available at: `http://localhost:8000`

---

## Step 2: Test Endpoints in Postman

### Endpoint 1: Health Check

**Method:** `GET`  
**URL:** `http://localhost:8000/health/ready`

**Headers:** None required

**Expected Response:**
```json
{
  "status": "ready"
}
```

**Postman Setup:**
1. Create a new request
2. Set method to `GET`
3. Enter URL: `http://localhost:8000/health/ready`
4. Click "Send"

---

### Endpoint 2: Query Database (Main Endpoint)

**Method:** `POST`  
**URL:** `http://localhost:8000/v1/query`

**Headers:**
```
Content-Type: application/json
```

**Request Body (JSON):**
```json
{
  "db_id": "mydb",
  "question": "Show me all call data"
}
```

**Expected Response:**
```json
{
  "sql": "SELECT * FROM chatbot.call_data LIMIT 1000;",
  "results": [
    {
      "id": 1,
      "call_id": "CALL001",
      "filename": "call_001.wav",
      ...
    }
  ],
  "error": null
}
```

**Postman Setup:**
1. Create a new request
2. Set method to `POST`
3. Enter URL: `http://localhost:8000/v1/query`
4. Go to "Headers" tab
5. Add header:
   - Key: `Content-Type`
   - Value: `application/json`
6. Go to "Body" tab
7. Select "raw" and "JSON" from dropdown
8. Paste the JSON body:
   ```json
   {
     "db_id": "mydb",
     "question": "Show me all call data"
   }
   ```
9. Click "Send"

---

## Example Queries for Your Database

Based on your `chatbot.call_data` table, here are some example queries:

### Example 1: List all records
```json
{
  "db_id": "mydb",
  "question": "List all call data"
}
```

### Example 2: Filter by agent
```json
{
  "db_id": "mydb",
  "question": "Show me calls handled by agent John"
}
```

### Example 3: Filter by date
```json
{
  "db_id": "mydb",
  "question": "Get all calls from today"
}
```

### Example 4: Aggregate data
```json
{
  "db_id": "mydb",
  "question": "What is the average call score?"
}
```

### Example 5: Count records
```json
{
  "db_id": "mydb",
  "question": "How many calls are there in total?"
}
```

### Example 6: Filter by score
```json
{
  "db_id": "mydb",
  "question": "Show me calls with score above 80"
}
```

---

## Response Format

### Success Response:
```json
{
  "sql": "SELECT * FROM chatbot.call_data WHERE call_score > 80 LIMIT 1000;",
  "results": [
    {
      "id": 1,
      "call_id": "CALL001",
      "call_score": 85,
      ...
    }
  ],
  "error": null
}
```

### Error Response:
```json
{
  "sql": "SELECT * FROM invalid_table;",
  "results": null,
  "error": "Table 'invalid_table' does not exist"
}
```

---

## Postman Collection Setup

### Create a Collection:

1. Click "New" → "Collection"
2. Name it: "Gen-SQL Backend API"
3. Add the two requests above to this collection

### Environment Variables (Optional):

Create an environment with:
- `base_url`: `http://localhost:8000`
- `db_id`: `mydb`

Then use in requests:
- URL: `{{base_url}}/v1/query`
- Body: `{"db_id": "{{db_id}}", "question": "..."}`

---

## Troubleshooting

### Server not responding?
- Check if server is running: `http://localhost:8000/health/ready`
- Check terminal for error messages
- Verify port 8000 is not in use

### Getting 422 Validation Error?
- Make sure `Content-Type: application/json` header is set
- Verify JSON body is valid JSON
- Check that `db_id` and `question` fields are present

### Getting 500 Internal Server Error?
- Check server logs in terminal
- Verify database connection in `.env` file
- Make sure schema has been refreshed: `python refresh_db.py`

### No results returned?
- Check if the generated SQL is correct in the response
- Verify the question matches your database schema
- Check database has data in the tables

---

## Quick Test Checklist

- [ ] Server is running on port 8000
- [ ] Health check endpoint returns `{"status": "ready"}`
- [ ] Database schema is refreshed (`python refresh_db.py`)
- [ ] `.env` file has correct `DATABASE_URL`
- [ ] Postman request has correct headers
- [ ] JSON body is properly formatted

