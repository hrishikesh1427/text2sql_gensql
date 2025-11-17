# Minimal integration test (requires running app + db)
import requests
def test_health():
    r = requests.get('http://localhost:8000/health/ready')
    assert r.status_code == 200
