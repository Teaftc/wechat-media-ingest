import hashlib
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from wechat_media_ingest.download.assets import download_file

PAYLOAD = b"\x00\x00\x00\x18ftypmp42" + b"v" * 128


class RangeHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        start = 0
        range_header = self.headers.get("Range")
        if range_header:
            start = int(range_header.removeprefix("bytes=").split("-", 1)[0])
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{len(PAYLOAD) - 1}/{len(PAYLOAD)}")
        else:
            self.send_response(200)
        body = PAYLOAD[start:]
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


def test_stream_download_resumes_part_file(tmp_path, monkeypatch):
    server = ThreadingHTTPServer(("127.0.0.1", 0), RangeHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    destination = tmp_path / "video.mp4"
    destination.with_name("video.mp4.part").write_bytes(PAYLOAD[:20])
    monkeypatch.setattr("wechat_media_ingest.download.assets.validate_public_url", lambda url, hosts: url)
    monkeypatch.setattr("wechat_media_ingest.download.assets.redirect_target", lambda current, location, hosts: location)
    try:
        info = download_file(
            f"http://127.0.0.1:{server.server_port}/video.mp4",
            destination,
            allowed_hosts={"127.0.0.1"},
            kind="video",
            expected_size=len(PAYLOAD),
        )
    finally:
        server.shutdown()
        thread.join(timeout=5)
    assert destination.read_bytes() == PAYLOAD
    assert info["sha256"] == hashlib.sha256(PAYLOAD).hexdigest()
    assert not destination.with_name("video.mp4.part").exists()
