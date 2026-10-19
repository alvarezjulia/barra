"""
Fake Garmin: reproduces just enough of Connect to test garmin.py without
touching the real account or depending on the network.

Serves a page that makes an authenticated call (with connect-csrf-token, like
the real web app) and exposes /gc-api/workout-service/{workout,schedule/<id>},
which return 403 if the CSRF token is missing.

    python3 tests/mock_garmin.py &
    ./garmin.py tests/fixtures/session.json --base http://127.0.0.1:8100 --debug
"""
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

CSRF = "test-csrf-123"

PAGE = """<!DOCTYPE html><meta charset=utf-8><title>Workouts</title>
<h1>My workouts</h1>
<script>
// Like the real web app: an authenticated call right after loading.
fetch('/gc-api/workout-service/workouts?start=1&limit=20', {headers: {
  'connect-csrf-token': '%s', 'NK': 'NT', 'X-app-ver': '5.27.2.1'
}}).then(r => r.json()).then(j => console.log('list', j));
</script>""" % CSRF

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _send(self, code, body, ctype="application/json"):
        raw = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path.startswith("/modern"):
            return self._send(200, PAGE, "text/html; charset=utf-8")
        if self.path.startswith("/gc-api/workout-service/workouts"):
            return self._send(200, json.dumps([]))
        self._send(404, "{}")

    def do_POST(self):
        auth = self.headers.get("connect-csrf-token")
        n = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(n).decode() if n else ""
        if auth != CSRF:
            return self._send(403, json.dumps({"message": "HTTP 403 Forbidden",
                                               "error": "ForbiddenException"}))
        if self.path == "/gc-api/workout-service/workout":
            w = json.loads(body)
            steps = w["workoutSegments"][0]["workoutSteps"]
            print(f"[mock] workout received: {w['workoutName']} with {len(steps)} root steps", flush=True)
            return self._send(200, json.dumps({"workoutId": 4242, "workoutName": w["workoutName"]}))
        if self.path.startswith("/gc-api/workout-service/schedule/"):
            print(f"[mock] scheduled: {body}", flush=True)
            return self._send(200, json.dumps({"scheduleId": 1}))
        self._send(404, "{}")

if __name__ == "__main__":
    HTTPServer(("127.0.0.1", 8100), H).serve_forever()
