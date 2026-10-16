from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_health():
    # 用子集断言,不写死整个字典:响应里除 status 外还有 service(服务身份标识,
    # 见 backend/main.py)。写死的话每次加字段都要改测试,而这里真正关心的是
    # "健康检查能通"这一件事。
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["service"] == "evalflow"
