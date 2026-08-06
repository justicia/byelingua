import hmac
import os
from http.server import BaseHTTPRequestHandler
from api.index import paris_schedule_due, run_scheduled_updates


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
            if not paris_schedule_due():
                body = b"Skipped: it is not 09:00 in Europe/Paris."
            else:
                result = run_scheduled_updates()
                body = (
                    f"Paris date {result['paris_date']}; public {result['public_processed']}; "
                    f"subscriber articles {result['personal_processed']}; users {result['users']}; "
                    f"already run {result['already_run']}."
                ).encode("utf-8")
            self.send_response(200)
        except Exception as error:
            body = str(error).encode("utf-8")
            self.send_response(500)

        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
