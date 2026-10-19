#!/usr/bin/env bash
# Runs a GraphQL query against WodUp from inside the already logged-in page.
#
#   wodup/gq.sh <OperationName> <file.graphql> <variablesJSON> <output.json>
#
# The fetch runs *inside* the tab (not from curl) because the session lives in
# an httpOnly + secure cookie: replicating it outside the browser isn't worth it.
#
# `browse js` doesn't await, so the response is parked in window.__out and
# polled until it stops being PENDING.
set -uo pipefail

B="${BROWSE:-$HOME/.claude/skills/gstack/browse/dist/browse}"
HERE="$(cd "$(dirname "$0")" && pwd)"
# cookies.py needs `cryptography`, which lives in the project venv, not in the
# system python3.
VENV_PY="$HERE/../.venv/bin/python"
[ -x "$VENV_PY" ] && PY="${PY:-$VENV_PY}"

OP="$1"; QUERY="$2"; VARS="${3:-{\}}"; OUTPUT="$4"

# browse only reads/writes under cwd or /tmp: a mktemp -d lands in /var/folders
# and the dump is silently dropped. The temp files live next to the script, and
# the cookie file is always deleted (it carries the session).
RUNNER="$HERE/_run.js"; RAW="$HERE/_response.json"; COOKIES="$HERE/_cookies.json"
trap 'rm -f "$RUNNER" "$RAW" "$COOKIES"' EXIT

url() { "$B" url 2>/dev/null | tail -1; }

# The fetch uses a relative path, so the tab must be on the WodUp origin. If
# the daemon restarted it sits on about:blank.
case "$(url)" in https://www.wodup.com/*) ;; *) "$B" goto https://www.wodup.com/ >/dev/null 2>&1 ;; esac

# Without a session, www.wodup.com redirects to the public site. It happens
# every time the browse daemon restarts: it wipes the cookies. It recovers on
# its own by pulling the cookie from your Chrome (see cookies.py).
if [[ "$(url)" == *about.wodup.com* ]]; then
  echo "WodUp session expired in browse: re-importing it from Chrome..." >&2
  "${PY:-python3}" "$HERE/cookies.py" > "$COOKIES" || exit 1
  "$B" goto https://www.wodup.com/login >/dev/null 2>&1
  "$B" cookie-import "$COOKIES" >/dev/null 2>&1
  "$B" goto https://www.wodup.com/ >/dev/null 2>&1
  [[ "$(url)" == *about.wodup.com* ]] && { echo "FAILED: no session in Chrome either. Log in at wodup.com and retry." >&2; exit 1; }
fi


python3 - "$QUERY" "$OP" "$VARS" "$RUNNER" <<'PY'
import json, sys
query_file, op, variables, dest = sys.argv[1:5]
template = """
window.__out = 'PENDING';
(async () => {
  const r = await fetch('/api/graphql?op=%s', {
    method: 'POST', credentials: 'include',
    headers: {'content-type': 'application/json'},
    body: JSON.stringify({operationName: %s, query: %s, variables: %s})
  });
  window.__out = await r.text();
})().catch(e => { window.__out = JSON.stringify({fetchError: String(e)}); });
'started'
"""
open(dest, 'w').write(template % (
    op, json.dumps(op), json.dumps(open(query_file).read()), variables))
PY

"$B" eval "$RUNNER" >/dev/null 2>&1
for _ in $(seq 1 60); do
  [ "$("$B" js "window.__out === 'PENDING' ? 'P' : 'D'" 2>/dev/null)" = "D" ] && break
done
"$B" js "window.__out" --out "$RAW" --raw >/dev/null 2>&1

# The output is only overwritten if the response carries data. A network or
# session error must not wipe out a good dump from an earlier month.
python3 - "$RAW" "$OUTPUT" <<'PY'
import json, shutil, sys
src, dest = sys.argv[1:3]
try:
    d = json.load(open(src))
except Exception as e:
    sys.exit(f"FAILED: unreadable response ({e}). {dest} left untouched.")
if "errors" in d:
    sys.exit("FAILED: " + json.dumps(d["errors"])[:400] + f"\n{dest} left untouched.")
if "fetchError" in d:
    sys.exit(f"FAILED: {d['fetchError']}\n{dest} left untouched.")
if not d.get("data"):
    sys.exit(f"FAILED: the response has no 'data'. {dest} left untouched.")
shutil.copy(src, dest)
print(f"OK -> {dest}")
PY
