Quick run notes:
1. Create .env from .env.example
2. pip install -r requirements.txt
3. uvicorn main:app --reload
4. POST /v1/query with JSON {"db_id":"mydb","question":"List users who placed orders above 1000"}
