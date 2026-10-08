from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_datasets_crud():
    r = client.post("/datasets", json={"name": "t", "description": "d"})
    assert r.status_code == 200 and r.json()["name"] == "t"
    did = r.json()["id"]
    r = client.post(f"/datasets/{did}/items", json={"input": "q", "expected_output": "a/b", "bucket": "x"})
    assert r.status_code == 200
    assert client.get("/datasets").json()
