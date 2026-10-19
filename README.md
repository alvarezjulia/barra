# Barra

[![tests](https://github.com/alvarezjulia/barra/actions/workflows/tests.yml/badge.svg)](https://github.com/alvarezjulia/barra/actions/workflows/tests.yml)

Weightlifting programs are written in percentages (`Snatch 5x2 @ 80%`), so every
session starts with mental math: which kilos, and which plates on each side.
Barra does that for you, from your coach's program on [WodUp](https://www.wodup.com)
all the way to your Garmin watch.

```
WodUp (% of 1RM) ──► barra.html ──► kilos + plates ──► garmin.py ──► Garmin watch
        │                                                             with timers
        └──► wodup/ ──► your history, real working max ──► web/ (today's weights on your phone)
```

## What's in it

| | |
|---|---|
| `barra.html` | The calculator. One file, no dependencies, works offline on a phone. Paste a screenshot of the workout and get kilos and plates per side. |
| `garmin.py` | Turns the calculator's output into a Garmin strength workout and schedules it on your calendar. |
| `wodup/` | Downloads what you were programmed and what you lifted from WodUp, and works out your real working max per lift. |
| `web/` | A phone page with the week's weights already calculated, your history and a chat. |
| `tests/` | `make test`. |

Your own data (PRs, history, saved sessions) lives in `data/`, which is
ignored by git. Keep it as a separate private repo if you want it versioned.

## Just the calculator

Open [`barra.html`](barra.html) in any browser, or save it to your phone. In
**Settings**, paste a screenshot of your WodUp *PRs & Benchmarks* (or type your
maxes), your bar and your plates. Then paste a workout and press **Calculate**.
Nothing is sent anywhere: everything stays in your browser.

## Everything else

Needs Python 3.9+ and Node 18+. The WodUp sync also needs macOS, Google
Chrome (logged in to WodUp) and the `browse` headless browser from
[gstack](https://github.com/garrytan/gstack); point `BROWSE=` at it if it isn't
in the default `~/.claude/skills/gstack/browse/dist/browse`.

```bash
make setup     # virtualenv, dependencies and Chromium
make data      # creates data/athlete.json: put your PRs there
make login     # log in to Garmin Connect once, by hand
```

**To the watch.** In the calculator, **Copy JSON for the watch**, then:

```bash
pbpaste | ./garmin.py --schedule today
./garmin.py tests/fixtures/session.json --dry-run    # print the Garmin JSON, upload nothing
```

**Your real max.** PRs go stale: you rarely test a true single. Your history
knows better: kilos lifted ÷ the percentage you were programmed is the max your
coach is actually programming from. `make web` downloads this week and this
month from WodUp, rebuilds your history and writes `data/barra.html` (the
calculator with your numbers in it) and `data/web.json` (for the phone page).
It reads your WodUp session from Chrome, so you must be logged in there.
`make web` only fetches the current month; to load your earlier history once:

```bash
wodup/gq.sh Month wodup/queries/month.graphql '{"start":"2026-05-01","end":"2026-05-31"}' data/raw/2026-05.json
make history
```

**On your phone.** `web/index.html` is built to be published as a
[claude.ai artifact](https://claude.ai), with `data/web.json` served next to it
as `data.json`; the chat uses Claude through the artifact runtime. To look at
it locally (everything but the chat):
`cp data/web.json web/data.json && python3 -m http.server -d web`, then open
http://localhost:8000.

Where each kilo comes from, in order: what you type in Settings, then your
history if it is heavier than your PR, then your WodUp PR. The screen always
says which one. In a complex, the weakest lift sets the load. Plates are picked
from your real inventory, preferring fewer plates within ±1 kg (2% at most).

## How a workout maps to Garmin

| WodUp | Garmin |
|---|---|
| `4x1 @ 85/90/93%` | 4 sets with rest; the last load repeats |
| `Every 2 min (6 sets)`, one lift | repeat ×6 of a fixed 120 s step with exercise and load |
| `Every 2 min (6 sets)`, complex | repeat ×6, one step per lift plus estimated rest |
| `Rest 2:30` | 150 s rest step |
| no rest given | 90 s |

Garmin has no EMOM. With one lift the cadence is exact but the watch doesn't
count reps; `--emom reps` and `--emom fixed` change that trade-off.

## Troubleshooting

```bash
./garmin.py tests/fixtures/session.json --debug --no-headless   # watch the browser work
python3 tests/mock_garmin.py & ./garmin.py tests/fixtures/session.json --base http://127.0.0.1:8100
```

- **`Not signed in`**: run `make login` again.
- **`Module ... is missing`**: run `make setup`.

## Disclaimer

Not affiliated with WodUp or Garmin. Both integrations use the same private
endpoints their websites use, can break without notice, and may go against
their terms of service: use them with your own account at your own risk. Your
sessions never leave your machine.

Check every load before you lift it. This tool does arithmetic; it does not
know how you feel today.

## Contributing

Issues and pull requests are welcome. Run `make test` before sending one.
`CLAUDE.md` explains the less obvious decisions and what was learned the hard
way about the Garmin and WodUp websites.

## License

[MIT](LICENSE)
