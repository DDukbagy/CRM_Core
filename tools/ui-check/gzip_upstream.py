# Render(Cloudflare)처럼 br/gzip 압축 + 압축된 content-length 로 응답하는 가짜 백엔드
import gzip, json
from http.server import BaseHTTPRequestHandler, HTTPServer
try:
    import brotli
except ImportError:
    brotli = None
BODY = json.dumps({"id": "x", "role": "INSTRUCTOR", "instructor_bio": "10년차 KPGA 프로. 초보부터 싱글까지 체계적으로 지도합니다." * 3,
                   "certifications": "KPGA 정회원", "birth_date": None, "tail": "끝"}, ensure_ascii=False).encode()
class H(BaseHTTPRequestHandler):
    def do_GET(self):
        enc = "br" if brotli and "br" in self.headers.get("Accept-Encoding", "") else "gzip"
        z = brotli.compress(BODY) if enc == "br" else gzip.compress(BODY)
        self.send_response(200); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Encoding", enc); self.send_header("Content-Length", str(len(z))); self.end_headers(); self.wfile.write(z)
    def log_message(self, *a): pass
HTTPServer(("127.0.0.1", 8099), H).serve_forever()
