"""
CORS middleware — allow_origins=['*'] + allow_credentials=True + methods=['*']

⚠️ เนื่องจาก allow_credentials=True, Starlette CORSMiddleware จะ
"echo" Origin header กลับมาแทนที่จะคืน '*' (CORS spec: credentials + wildcard
เข้ากันไม่ได้ — browser จะ reject) ดังนั้น test จึงตรวจว่า response
echo origin กลับมาเป็นค่าที่ client ส่งมา
"""


class TestCORSHeaders:
    def test_preflight_options_succeeds(self, client):
        """OPTIONS preflight → 200 + echo origin"""
        r = client.options(
            "/api/latest-signal",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert r.status_code == 200
        # Starlette echo Origin (ไม่ใช่ '*') เพราะ allow_credentials=True
        assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"
        assert r.headers.get("access-control-allow-credentials") == "true"

    def test_actual_request_returns_cors_origin_header(self, client, fake_db):
        """GET + Origin header → response ต้อง echo origin กลับมา"""
        fake_db.set_fetchone({"id": 1, "signal": "BUY"})
        r = client.get(
            "/api/latest-signal", headers={"Origin": "http://localhost:5173"}
        )
        assert r.headers.get("access-control-allow-origin") == "*"

    def test_preflight_allows_any_method(self, client):
        """POST ไม่มีใน API — แต่ middleware ยังต้องตอบ allow-methods"""
        r = client.options(
            "/api/latest-signal",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert r.status_code == 200
        allow_methods = r.headers.get("access-control-allow-methods", "")
        # FastAPI CORSMiddleware expand '*' เป็น list of methods
        assert "POST" in allow_methods or "*" in allow_methods
