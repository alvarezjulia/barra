# CLAUDE.md

Context for Claude Code. What this is and how to use it: `README.md`. This file
holds what you can't read off the code and took effort to find out. **Don't
rediscover it.**

Anything about whoever uses the repo (athlete, links, terminal quirks) goes in
`CLAUDE.local.md`, which is never committed.

## Garmin

- The endpoint is **`/gc-api/workout-service/workout`**. The path without
  `gc-api` returns 403/404. `garmin.py` infers the API root from the site's own
  calls instead of hard-coding it.
- **Connect does not use `Authorization: Bearer`** on its website: it
  authenticates by cookie. What's in `localStorage` (`JetLagToken`,
  `HereToken`) belongs to HERE Maps and is useless here.
- POSTs need **`connect-csrf-token`**, found in the headers of any data call
  the site makes.
- Even with the CSRF token, **replaying a request from outside the browser
  returns 403** (origin, referer and sec-fetch-* are missing). That's why the
  fetch runs inside the page.
- **`garminconnect` gets a 429 per account, not per IP** (tied to the clientId
  of its "mobile"/"portal" logins;
  [issue #344](https://github.com/cyberjunky/python-garminconnect/issues/344)).
  Switching networks doesn't help and it lasts days. Hence uploading through a
  real browser: the widget SSO login doesn't touch that counter. The API path
  was removed from the repo.
- Website routes are `/app/*`; `/modern/*` redirects.
- The Vivoactive 5 **does show the target weight** next to the reps.

## WodUp

There's no public API, but the website is Apollo GraphQL and **introspection
is enabled**.

- `POST https://www.wodup.com/api/graphql?op=<Operation>`. The `op` **must
  match** the operation name in the document or it errors out.
- Logged results: `currentUser.results(startDate, endDate)`. Programmed (not
  done yet): `currentUser.activityTimeline(...).subscribedWods[].wodComponents[].workout`.
  In both, `workout.details.movements[]` has `load` + `loadUnit: "%1rm"`.
- Auth is the **`session_token` cookie, httpOnly**: JavaScript can't read it.
  `wodup/cookies.py` reads it from Chrome and decrypts it; `gq.sh` re-imports
  it only when the `browse` daemon restarts and loses the session.
  `browse cookie-import-browser` imports 0 cookies: not the way.
- The macOS keychain asks for permission **once per binary** ("Chrome Safe
  Storage"): allowing `security` doesn't allow Python.
- `browse js` doesn't await: `gq.sh` parks the response in `window.__out` and
  polls.

## Non-obvious decisions

**Implied max = kilos ÷ programmed %.** It's the max the coach is actually
programming from. It gets skewed when the athlete went above or below the
plan that day: it's for consistent loads, not a record. **Exception: a max
test** (a single at ≥100% that isn't a pull): there the max is what was
lifted. Dividing by 105% produced a max 5% short that doesn't exist.

**`HIST_MAXES` (`wodup/rms.py`) only includes lifts whose % is of their own
1RM.** The RDL is programmed at 50% *of the deadlift*: it gave a 130 kg "RDL
max" and 91 kg on the bar at 70%. Pulls, same. There's a whitelist and a 1.6×
PR cap. **Before adding a lift to the whitelist, check which max it's
programmed from.**

**The phone page also uses the median of the last 3 sessions of the same
lift** (by WodUp id) for lifts barra.html doesn't know. That's fine for pulls:
a Clean Pull at 105% done with 60 kg says the base is 57.1, and it's applied to
the next Clean Pull. Complexes without history borrow from the closest family
and the page marks them "approximate".

**`S.manual[key]`** marks a max typed by hand in Settings; without it, the
history would silently overwrite the edit.

**The weakest link sets the load in a complex.** `3 Front Squats + 1 Jerk @
70%` comes from the jerk. If that breaks, it's 27 kg too much. There are tests.

**`RM_SUBSTITUTE` is short on purpose**: only pairs where the borrowed max is
not above the real one. A Power Snatch doesn't borrow from the Snatch; a
Snatch Balance doesn't borrow from the Overhead Squat.

**EMOM → Garmin** (`build_block`): one lift → a fixed-duration step (exact
cadence, reps not counted). Complex → rep steps + rest estimated at 4 s/rep
(approximate cadence). Still to be tried at the gym to see which feels better.

## Conventions

- English everywhere. Comments explain **why**, and several document a failed
  attempt.
- **No silent failures**: a missing max, an approximate exercise name or an
  estimated cadence is always reported. Never make up a number.
- The pure logic of `barra.html` lives between `LOGIC START/END` and never
  touches the DOM. `tests/extract-logic.mjs` copies it to `tests/logic.mjs`
  (used by the tests and `web/build.mjs`).
- Code lives in the root, `wodup/` and `web/`; everything personal in `data/`,
  which is gitignored (a separate private repo). `barra.html` ships with empty
  `SEED_MAXES`/`HIST_MAXES`; `wodup/rms.py` writes the personal copy to
  `data/barra.html`. Never put anyone's data in code or tests (tests use
  `tests/fixtures/athlete.mjs`).
- The browser profile (`~/.garmin-browser-profile`) holds the Garmin session.
  Never commit it.

## To do

- **Metcons**: the parser doesn't understand AMRAPs, rounds or time caps.
- No FIT equivalent (mapped to the closest one, with a warning): Snatch
  Balance, Muscle Snatch/Clean, Sots Press, pulls.
