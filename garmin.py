#!/usr/bin/env python3
"""
From barra.html's JSON to a strength workout in Garmin Connect, scheduled on
the calendar so it syncs down to the watch.

    ./garmin.py --login                                  # once: you sign in by hand
    ./garmin.py tests/fixtures/session.json --schedule today
    pbpaste | ./garmin.py --schedule tomorrow
    ./garmin.py tests/fixtures/session.json --dry-run     # the JSON, uploads nothing

Two halves: build_workout() translates (pure, tested) and push() uploads.

Why upload through a browser and not the API: `garminconnect` gets a 429 on
login and the limit is PER ACCOUNT (tied to the clientId of its login
strategies), so changing IP does nothing and it can last for days. The browser
login is the widget SSO flow, which doesn't touch that counter. The profile
lives in ~/.garmin-browser-profile and after the first login everything runs
headless.
"""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import os
import pathlib
import re
import sys
from typing import Any

PROFILE = os.path.expanduser(os.getenv("GARMIN_PROFILE", "~/.garmin-browser-profile"))
BASE = os.getenv("GARMIN_BASE", "https://connect.garmin.com")

# ===========================================================================
# Translation: barra.html JSON -> Garmin workout
# ===========================================================================

# Names from Garmin's FIT SDK (*_exercise_name enums). Weightlifting isn't fully
# covered: anything missing maps to the closest one (approx=True) with a warning.
EXERCISES: dict[str, tuple[str, str | None, bool]] = {
    # key                  category           FIT name                    approx
    "back_squat":         ("SQUAT",          "BARBELL_BACK_SQUAT",        False),
    "front_squat":        ("SQUAT",          "BARBELL_FRONT_SQUAT",       False),
    "ohs":                ("SQUAT",          "OVERHEAD_BARBELL_SQUAT",    False),
    "squat_snatch":       ("SQUAT",          "BARBELL_SQUAT_SNATCH",      False),
    "thruster":           ("SQUAT",          "THRUSTERS",                 False),

    "snatch":             ("OLYMPIC_LIFT",   "BARBELL_SNATCH",            False),
    "power_snatch":       ("OLYMPIC_LIFT",   "BARBELL_POWER_SNATCH",      False),
    "clean":              ("OLYMPIC_LIFT",   "CLEAN",                     False),
    "power_clean":        ("OLYMPIC_LIFT",   "BARBELL_POWER_CLEAN",       False),
    "squat_clean":        ("OLYMPIC_LIFT",   "BARBELL_SQUAT_CLEAN",       False),
    "clean_jerk":         ("OLYMPIC_LIFT",   "CLEAN_AND_JERK",            False),
    "push_jerk":          ("OLYMPIC_LIFT",   "PUSH_JERK",                 False),
    "split_jerk":         ("OLYMPIC_LIFT",   "SPLIT_JERK",                False),
    "jerk":               ("OLYMPIC_LIFT",   "SPLIT_JERK",                True),
    "snatch_pull":        ("OLYMPIC_LIFT",   "BARBELL_HIGH_PULL",         True),
    "clean_pull":         ("OLYMPIC_LIFT",   "BARBELL_HIGH_PULL",         True),
    "muscle_snatch":      ("OLYMPIC_LIFT",   "BARBELL_SNATCH",            True),
    "muscle_clean":       ("OLYMPIC_LIFT",   "CLEAN",                     True),
    "snatch_balance":     ("OLYMPIC_LIFT",   None,                        True),

    "deadlift":           ("DEADLIFT",       "BARBELL_DEADLIFT",          False),
    "rdl":                ("DEADLIFT",       "ROMANIAN_DEADLIFT",         False),

    "push_press":         ("SHOULDER_PRESS", "BARBELL_PUSH_PRESS",        False),
    "strict_press":       ("SHOULDER_PRESS", "STRICT_PRESS",              False),
    "sots_press":         ("SHOULDER_PRESS", "OVERHEAD_BARBELL_PRESS",    True),

    "bench":              ("BENCH_PRESS",    "BARBELL_BENCH_PRESS",       False),
    "good_morning":       ("LEG_CURL",       "GOOD_MORNING",              False),
    "ghd_hip_ext":        ("HYPEREXTENSION", "STATIC_BACK_EXTENSION",     True),
    "ghd_situp":          ("SIT_UP",         None,                        True),
}

STRENGTH = {"sportTypeId": 5, "sportTypeKey": "strength_training"}
KILOGRAM = {"unitId": 8, "unitKey": "kilogram", "factor": 1000.0}
STEP_INTERVAL = {"stepTypeId": 3, "stepTypeKey": "interval"}
STEP_REST = {"stepTypeId": 5, "stepTypeKey": "rest"}
STEP_REPEAT = {"stepTypeId": 6, "stepTypeKey": "repeat"}
END_TIME = {"conditionTypeId": 2, "conditionTypeKey": "time"}
END_ITERATIONS = {"conditionTypeId": 7, "conditionTypeKey": "iterations"}
END_REPS = {"conditionTypeId": 10, "conditionTypeKey": "reps"}

DEFAULT_REST = 90          # when the WOD doesn't say
SEC_PER_REP = 4            # to estimate the rest gap inside an EMOM


class Builder:
    """Collects steps with a global, consecutive stepOrder, plus warnings and notes."""

    def __init__(self) -> None:
        self.n = 0
        self.warn: list[str] = []
        self.notes: list[str] = []

    def order(self) -> int:
        self.n += 1
        return self.n

    def exercise(self, key: str | None, label: str) -> dict[str, Any]:
        if not key or key not in EXERCISES:
            self.warn.append(f"'{label}' is not in my catalog: it goes as a generic step with no exercise name.")
            return {"category": "TOTAL_BODY"}
        category, name, approx = EXERCISES[key]
        if approx:
            shown = (name or category).replace("_", " ").title()
            self.warn.append(f"'{label}' doesn't exist in Garmin's catalog: the watch will show it as '{shown}'.")
        return {"category": category, **({"exerciseName": name} if name else {})}

    def work(self, part: dict[str, Any], kg: float, *, reps: int | None = None,
             seconds: int | None = None) -> dict[str, Any]:
        """Step with exercise and weight. Ends by reps or, in an EMOM, by time."""
        end, value = (END_TIME, seconds) if seconds else (END_REPS, reps)
        return {
            "type": "ExecutableStepDTO", "stepOrder": self.order(), "stepType": STEP_INTERVAL,
            "endCondition": end, "endConditionValue": float(value),
            "weightValue": float(kg), "weightUnit": KILOGRAM,
            **self.exercise(part.get("key"), part.get("label", "?")),
        }

    def rest(self, seconds: int) -> dict[str, Any]:
        return {
            "type": "ExecutableStepDTO", "stepOrder": self.order(), "stepType": STEP_REST,
            "endCondition": END_TIME, "endConditionValue": float(seconds),
        }


def build_block(block: dict[str, Any], b: Builder, emom_mode: str = "time") -> list[dict[str, Any]]:
    """
    One workout block -> Garmin steps.

    Garmin has no EMOM. Three translations (--emom):

      · time (default): single movement with an interval -> one fixed-duration
        step equal to the interval, with exercise and weight. Cadence is exact;
        the watch doesn't count reps. A complex can't fit two exercises in one
        step, so it falls back to splitting by reps.
      · reps: single movements also go by reps + estimated rest.
      · fixed: the whole set lasts exactly the interval, complexes included.
        The watch only shows weight and time, but the cycle never drifts.
    """
    # A load with no lift (a bare "4x3 @ 70kg") still becomes a step with that
    # weight; with no parts at all it used to turn into a repeat of rests only.
    parts = block.get("parts") or [{"key": block.get("governing"), "label": block["title"]}]
    loads = block.get("loads") or []
    if not loads:
        return []

    interval = block.get("intervalSec")
    sets = block.get("sets") or len(loads)
    rest = block.get("restSec")
    reps_of = lambda p: p.get("reps") or block.get("reps") or 1   # noqa: E731
    title = block["title"]

    # Ramp (85/90/93%): each load is its own set, no repeat group.
    if len(loads) > 1:
        # "4x1 @ 85/90/93%" is 4 sets and 3 weights: the last one repeats.
        if sets > len(loads):
            b.notes.append(f"{title}: {sets} sets and {len(loads)} weights;"
                           f" repeating the last one ({loads[-1]['kg']} kg) to fill them.")
            loads = loads + [loads[-1]] * (sets - len(loads))
        steps = []
        for i, load in enumerate(loads):
            for part in parts:
                steps.append(b.work(part, load["kg"], reps=reps_of(part)))
            if i < len(loads) - 1:
                steps.append(b.rest(rest or interval or DEFAULT_REST))
        return steps

    kg = loads[0]["kg"]
    if sets <= 1:
        return [b.work(p, kg, reps=reps_of(p)) for p in parts]

    group_order = b.order()
    single = len(parts) == 1
    if interval and (emom_mode == "fixed" or (single and emom_mode == "time")):
        # In a complex a step can't carry two exercises: it's labelled with the
        # governing one and the rep breakdown goes in the note.
        lead = parts[0] if single else {"key": block.get("governing"), "label": title}
        inner = [b.work(lead, kg, seconds=interval)]
        what = (f"{reps_of(parts[0])} reps per block" if single else
                " + ".join(f"{reps_of(p)} {p.get('label', '?')}" for p in parts) + f" @ {kg} kg")
        b.notes.append(f"{title}: {sets} × {interval}s on the dot ({what}); the watch doesn't count reps.")
    else:
        inner = [b.work(p, kg, reps=reps_of(p)) for p in parts]
        if interval:
            gap = max(10, interval - sum(reps_of(p) for p in parts) * SEC_PER_REP)
            b.notes.append(f"{title}: complex inside a {interval}s EMOM."
                           f" Rest estimated at {gap}s ({SEC_PER_REP}s/rep); cadence is approximate.")
        else:
            gap = rest or DEFAULT_REST
            if not rest:
                b.notes.append(f"{title}: the WOD gives no rest; using {DEFAULT_REST}s between sets.")
        inner.append(b.rest(gap))

    return [{
        "type": "RepeatGroupDTO", "stepOrder": group_order, "stepType": STEP_REPEAT,
        "numberOfIterations": sets, "endCondition": END_ITERATIONS,
        "endConditionValue": float(sets), "skipLastRestStep": True, "workoutSteps": inner,
    }]


def build_workout(session: dict[str, Any], name: str, emom_mode: str = "time",
                  rest_between_blocks: int = 0) -> tuple[dict[str, Any], list[str], list[str]]:
    b = Builder()
    steps: list[dict[str, Any]] = []
    for block in session.get("blocks", []):
        block_steps = build_block(block, b, emom_mode)
        # A block with no loads (GHD...) produces no steps and no gap before the next one.
        if rest_between_blocks and steps and block_steps:
            steps.append(b.rest(rest_between_blocks))
        steps.extend(block_steps)
    if rest_between_blocks and steps:
        b.notes.append(f"{rest_between_blocks}s gap between blocks to change weights.")
    if not steps:
        raise SystemExit("The JSON has no block with a load. Did you hit Calculate before copying?")

    return ({
        "workoutName": name[:80],
        "sportType": STRENGTH,
        "workoutSegments": [{"segmentOrder": 1, "sportType": STRENGTH, "workoutSteps": steps}],
    }, b.warn, b.notes)


def default_name(session: dict[str, Any], when: str | None = None) -> str:
    """Short and sortable: the watch list shows the date, not half a truncated title."""
    return f"Weightlifting {when or dt.date.today().isoformat()} ({len(session.get('blocks', []))} blocks)"


def parse_date(value: str) -> str:
    today = dt.date.today()
    v = value.strip().lower()
    if v == "today":
        return today.isoformat()
    if v == "tomorrow":
        return (today + dt.timedelta(days=1)).isoformat()
    return dt.date.fromisoformat(value).isoformat()


# ===========================================================================
# Upload: real browser with the saved session
# ===========================================================================

# Static assets and telemetry: never the request we're after.
NOISE = re.compile(
    r"\.(js|mjs|css|png|jpe?g|gif|svg|ico|woff2?|ttf|properties)(\?|$)"
    r"|/static/|/web-react/|/web-translations/|cdn-cgi|sentry|google|doubleclick",
    re.I,
)


def open_context(pw, headless: bool):
    exe = os.getenv("PLAYWRIGHT_CHROMIUM")   # only for setups with Chromium in a non-standard place
    return pw.chromium.launch_persistent_context(
        PROFILE, headless=headless, viewport={"width": 1280, "height": 900},
        args=["--disable-blink-features=AutomationControlled"],
        **({"executable_path": exe} if exe else {}),
    )


def logged_in(page) -> bool:
    """Without a session, Connect bounces you to the SSO."""
    url = page.url.lower()
    return "sso" not in url and "signin" not in url


def do_login(base: str) -> int:
    from playwright.sync_api import sync_playwright

    print("Opening the browser. Sign in to your account at your own pace (MFA included).")
    print("Once you're inside Connect, close the window or press Enter here.")
    with sync_playwright() as pw:
        ctx = open_context(pw, headless=False)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(f"{base}/modern/", wait_until="domcontentloaded")
        try:
            input()
        except (EOFError, KeyboardInterrupt):
            pass
        ok = logged_in(page)
        ctx.close()
    if ok:
        print(f"Session saved to {PROFILE}.")
        return 0
    print("It doesn't look like the session got signed in. Try again.", file=sys.stderr)
    return 1


def capture_headers(ctx, page, base: str, timeout_ms: int, debug: bool):
    """
    Copies Garmin's own headers from one of the web app's data calls.

    Learned the hard way:
      · the listener goes on the CONTEXT: Connect fires requests from iframes.
      · Connect's web does NOT use Authorization: it authenticates by cookie.
        What needs copying is connect-csrf-token and friends.
      · /modern/* redirects to /app/*.
      · the API lives under /gc-api/, but the root is inferred from what's
        observed so it survives the next change.
    """
    candidates: list[tuple[str, dict[str, str]]] = []

    def on_request(req):
        if req.resource_type in ("xhr", "fetch") and not NOISE.search(req.url) \
                and (req.url.startswith(base) or "garmin" in req.url):
            candidates.append((req.url, {k.lower(): v for k, v in req.headers.items()}))

    ctx.on("request", on_request)
    for route in ("/app/workouts", "/app/calendar", "/modern/"):
        if candidates:
            break
        try:
            page.goto(f"{base}{route}", wait_until="domcontentloaded", timeout=timeout_ms)
            page.wait_for_load_state("networkidle", timeout=min(timeout_ms, 15000))
        except Exception as e:  # noqa: BLE001 — networkidle sometimes never arrives; what was captured is enough
            if debug:
                print(f"  ({route}: {e})", file=sys.stderr)
        waited = 0
        while not candidates and waited < timeout_ms:
            page.wait_for_timeout(500)
            waited += 500
    ctx.remove_listener("request", on_request)

    if not candidates:
        return {}, base + "/gc-api"

    # The best template is a call to the workout service itself.
    candidates.sort(key=lambda c: 0 if "/workout-service/" in c[0] else 1 if "/gc-api/" in c[0] else 2)
    url, h = candidates[0]
    root = url.split("/workout-service/")[0] if "/workout-service/" in url else base + "/gc-api"
    if debug:
        print(f"template: {url[:120]}\nAPI root: {root}", file=sys.stderr)

    # Origin, referer and sec-fetch-* are set by the browser, and better than we could.
    return {k: v for k, v in h.items()
            if v and (k.startswith("x-") or k in ("nk", "di-backend") or "csrf" in k)}, root


class Connect:
    """Authenticated Connect session. Calls are made FROM the page: replaying
    them from outside gave 403 even with the CSRF token, because origin,
    referer and sec-fetch-* are missing."""

    def __init__(self, base: str, headless: bool, timeout_ms: int, debug: bool):
        from playwright.sync_api import sync_playwright
        self.pw = sync_playwright().start()
        self.ctx = open_context(self.pw, headless=headless)
        self.page = self.ctx.pages[0] if self.ctx.pages else self.ctx.new_page()
        self.page.goto(f"{base}/modern/", wait_until="domcontentloaded")
        if not logged_in(self.page):
            self.close()
            raise SystemExit("Not signed in. Run first:  ./garmin.py --login")
        self.headers, self.root = capture_headers(self.ctx, self.page, base, timeout_ms, debug)
        if not self.headers:
            self.close()
            raise SystemExit("Didn't see any data call from the web app. Retry with --debug"
                             " --no-headless (if Garmin logged you out: --login again).")
        if debug:
            print(f"Garmin headers: {json.dumps(self.headers, indent=2)}", file=sys.stderr)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def close(self):
        self.ctx.close()
        self.pw.stop()

    def call(self, route: str, method: str = "POST", body: dict | None = None) -> tuple[int, str]:
        status, text = self.page.evaluate(
            """async ({url, method, body, headers}) => {
                const r = await fetch(url, {method, credentials: 'include', body: body ?? undefined,
                    headers: Object.assign({'Content-Type': 'application/json'}, headers)});
                return [r.status, await r.text()];
            }""",
            {"url": self.root + route, "method": method, "headers": self.headers,
             "body": None if body is None else json.dumps(body)},
        )
        if status >= 400:
            raise SystemExit(f"{method} {route} failed with {status}: {text[:600]}")
        return status, text


def push(gc: Connect, workout: dict[str, Any], when: str | None) -> None:
    _, text = gc.call("/workout-service/workout", "POST", workout)
    created = json.loads(text)
    wid = created.get("workoutId")
    print(f"Created '{created.get('workoutName')}' (id {wid})")
    if when:
        gc.call(f"/workout-service/schedule/{wid}", "POST", {"date": when})
        print(f"Scheduled for {when}. Sync the watch.")


# ===========================================================================
# CLI
# ===========================================================================

def _reexec_in_venv(module: str) -> None:
    """./garmin.py starts with the system Python: if the module is missing, it
    re-executes itself with the venv's instead of dying with ModuleNotFoundError."""
    if importlib.util.find_spec(module):
        return
    py = pathlib.Path(__file__).resolve().parent / ".venv" / "bin" / "python"
    if py.exists() and not os.environ.get("_BARRA_REEXEC") and str(py) != sys.executable:
        os.environ["_BARRA_REEXEC"] = "1"
        os.execv(str(py), [str(py), __file__, *sys.argv[1:]])
    raise SystemExit(f"Module '{module}' is missing. Run:  make setup")


def main() -> int:
    ap = argparse.ArgumentParser(description="Upload the barra.html workout to Garmin Connect.")
    ap.add_argument("file", nargs="?", help="barra.html JSON (default: stdin)")
    ap.add_argument("--login", action="store_true", help="sign in by hand (first time only)")
    ap.add_argument("--delete", metavar="WORKOUT_ID", help="delete a workout by id")
    ap.add_argument("--dry-run", action="store_true", help="print the Garmin JSON and upload nothing")
    ap.add_argument("--name", help="workout name")
    ap.add_argument("--schedule", metavar="DATE", help="today, tomorrow or YYYY-MM-DD")
    ap.add_argument("--emom", choices=["time", "reps", "fixed"], default="time",
                    help="how to translate an EMOM (see build_block)")
    ap.add_argument("--rest-between-blocks", type=int, default=0, metavar="SEC",
                    help="gap between one block and the next")
    ap.add_argument("--no-headless", action="store_true", help="watch the browser work")
    ap.add_argument("--debug", action="store_true")
    ap.add_argument("--timeout", type=int, default=30000, help="ms to capture a request from the web app")
    ap.add_argument("--base", default=BASE, help=argparse.SUPPRESS)  # for the test mock
    args = ap.parse_args()

    if not args.dry_run:
        _reexec_in_venv("playwright")
    if args.login:
        return do_login(args.base)
    if args.delete:
        with Connect(args.base, not args.no_headless, args.timeout, args.debug) as gc:
            gc.call(f"/workout-service/workout/{args.delete}", "DELETE")
        print(f"Deleted workout {args.delete}.")
        return 0

    raw = open(args.file, encoding="utf-8").read() if args.file else sys.stdin.read()
    if not raw.strip():
        raise SystemExit("Received nothing. Copy the JSON from the app and pass it via stdin or as a file.")
    session = json.loads(raw)
    when = parse_date(args.schedule) if args.schedule else None
    workout, warn, notes = build_workout(session, args.name or default_name(session, when),
                                         args.emom, args.rest_between_blocks)
    for n in notes:
        print(f"  · {n}", file=sys.stderr)
    for w in warn:
        print(f"  ! {w}", file=sys.stderr)

    if args.dry_run:
        print(json.dumps(workout, indent=2, ensure_ascii=False))
        return 0
    with Connect(args.base, not args.no_headless, args.timeout, args.debug) as gc:
        push(gc, workout, when)
    return 0


if __name__ == "__main__":
    sys.exit(main())
