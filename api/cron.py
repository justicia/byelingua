import hmac
import os
from http.server import BaseHTTPRequestHandler

from api.index import run_daily_digest


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        expected = os.environ.get("CRON_SECRET", "")
        supplied = self.headers.get("Authorization", "")
        authorized = expected and hmac.compare_digest(
            supplied,
            f"Bearer {expected}",
        )
        if not authorized:
            self.send_response(401)
            self.end_headers()
            return

        try:
            result = run_daily_digest()
            body = (
                f"Processed {result['processed']} articles; "
                f"{result['items']} stored articles."
            ).encode("utf-8")
            self.send_response(200)
        except Exception as error:
            body = str(error).encode("utf-8")
            self.send_response(500)

        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
