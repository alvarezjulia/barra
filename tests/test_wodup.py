"""Implied RM (wodup/normalize.py) and what goes into HIST_MAXES (wodup/rms.py)."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "wodup"))
from normalize import block_rm, to_kg  # noqa: E402
from rms import hist_maxes  # noqa: E402

P = lambda *pcts: [{"pct": p, "reps": 1} for p in pcts]   # noqa: E731
H = lambda *kgs: [{"kg": k} for k in kgs]                 # noqa: E731

cases = [
    ("working sets: kg ÷ %", block_rm(P(80, 80), H(32, 32), "Squat Snatch"), (40, 40, False)),
    ("ramp: working mode and top", block_rm(P(80, 80, 90), H(40, 40, 46), "Clean"), (50, 51.1, False)),
    ("max test: the RM is what was lifted", block_rm(P(105), H(75), "Front Squat"), (75, 75, True)),
    ("a pull at 120% is not a test", block_rm(P(120), H(60), "Clean Pull"), (50, 50, False)),
    ("no % means no RM", block_rm([{"pct": None, "reps": 15}], H(12.5), "GHD"), (None, None, False)),
]
cases += [
    ("ramp with no repeated set: the lower implied RM wins",
     block_rm(P(85, 90, 93), H(42, 45, 47), "Clean"), (49.4, 50.5, False)),
    ("pounds are converted to kilos", to_kg(100, "lb"), 45.4),
    ("kilos stay as they are", to_kg(60, "kg"), 60),
]
# hist_maxes: {WodUp name: [(date, implied RM, top)]}, PRs by key
S = lambda *kgs: [(f"2026-10-0{i + 1}", kg, kg) for i, kg in enumerate(kgs)]   # noqa: E731
hm, _ = hist_maxes({"Front Squat": S(80, 81), "Romanian Deadlift": S(120, 130),
                    "Clean Pull": S(57, 57), "Snatch": S(34), "Back Squat": S(85, 200)},
                   {"front_squat": 68, "back_squat": 72})
cases += [
    ("HIST_MAXES takes the latest session", hm.get("front_squat", {}).get("kg"), 81),
    ("RDL and pulls are left out (their % is of another RM)", sorted(hm), ["front_squat"]),
    ("a single session does not get in", "snatch" in hm, False),
    ("an implied RM > 1.6× the PR is discarded", "back_squat" in hm, False),
]
failures = [n for n, got, want in cases if got != want and print(f"FAIL  {n}: {got} != {want}") is None]
for n, got, want in cases:
    if got == want:
        print(f"  ok  {n}")
print("ALL OK" if not failures else f"{len(failures)} failures")
sys.exit(1 if failures else 0)
