#!/usr/bin/env python3
"""Turns the raw WodUp API dump into the normalized history.

Input:   data/raw/*.json   (responses to the `Month` query, one per month)
Output:  data/history.json + data/history.md + data/progression.md

The data point that matters is not just the kilos lifted: it is the kilos
*next to the percentage they were programmed at*. That pair gives the implied
RM the athlete actually worked with that day, which is the only thing that
explains why a 70% in May weighs 35 kg and a 70% in August also weighs 35 kg
even though the WodUp PR never moved.

The data folder defaults to <repo>/data and can be overridden with BARRA_DATA.
"""

import json
import glob
import os
from collections import defaultdict

DATA = os.environ.get("BARRA_DATA") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
RAW = os.path.join(DATA, "raw")


def load_results():
    res = []
    for path in sorted(glob.glob(os.path.join(RAW, "*.json"))):
        d = json.load(open(path))
        res += d["data"]["currentUser"]["results"]
    # sessionOrder orders the blocks within the day; prefix (A/B/C) is the label
    res.sort(key=lambda r: (r["doneOn"], r.get("sessionOrder") or 0, r.get("prefix") or ""))
    return res


def complex_parts(outputs, set_index):
    """The movements of a complex, in order, for a given set."""
    children = [
        o for o in outputs
        if o.get("detailsIndex") == set_index and o.get("complexIndex") is not None
    ]
    children.sort(key=lambda o: o["complexIndex"])
    return [
        {"name": o["movement"]["name"] if o["movement"] else None,
         "movementId": o["movement"]["id"] if o["movement"] else None,
         "reps": o["reps"]}
        for o in children
    ]


LB = 0.45359237


def to_kg(load, unit):
    """WodUp stores each set in the unit the athlete logs in. Pounds taken as
    kilos would make every implied max 2.2x too heavy."""
    if load is None:
        return None
    if unit in ("lb", "lbs"):
        return round(load * LB, 1)
    return load


def block_rm(programmed, done, name):
    """(implied RM, top RM, is a max test) for a block.

    Implied RM = kg / (pct/100): the RM actually worked with that day, which
    is often NOT the PR recorded in WodUp. Two readings, because on ramps they
    disagree: the mode is the working weight (on a tie the lower one wins:
    it's the conservative choice for what goes on the bar) and the top is the
    heaviest set.

    Exception: a single at 100% or more of a lift (not a pull) is a max test,
    and there the RM is what was lifted. Dividing it by 105% gave a 71.4 kg
    Front Squat on the day the athlete made 75 and missed 80: the rest of the
    week would have come out 5% short on an RM that does not exist.
    """
    pcts = [p["pct"] for p in programmed if p["pct"]]
    kgs = [h["kg"] for h in done if h["kg"]]
    if len(programmed) == 1 and pcts and pcts[0] >= 100 and kgs and "pull" not in name.lower():
        return max(kgs), max(kgs), True
    rms = [round(h["kg"] / (programmed[i]["pct"] / 100.0), 1)
           for i, h in enumerate(done)
           if i < len(programmed) and programmed[i]["pct"] and h["kg"]]
    if not rms:
        return None, None, False
    mode = min(set(rms), key=lambda rm: (-rms.count(rm), rm))
    return mode, max(rms), False


def normalize(res):
    days = defaultdict(list)

    for r in res:
        w = r.get("workout") or {}
        wdet = w.get("details") if isinstance(w.get("details"), dict) else {}
        rdet = r.get("details") if isinstance(r.get("details"), dict) else {}

        # Programmed: one entry per set, with the % of 1RM the coach set.
        programmed = []
        for m in (wdet.get("movements") or []):
            pct = None
            if m.get("loadUnit") == "%1rm" and m.get("load") not in (None, ""):
                try:
                    pct = float(m["load"])
                except (TypeError, ValueError):
                    pct = None
            reps = m.get("reps")
            try:
                reps = int(reps) if reps not in (None, "") else None
            except (TypeError, ValueError):
                pass
            programmed.append({"pct": pct, "reps": reps})

        # Done: the kilos actually moved, set by set.
        done = []
        for i, s in enumerate(rdet.get("sets") or []):
            done.append({
                "kg": to_kg(s.get("load"), s.get("loadUnit")),
                "unit": s.get("loadUnit"),
                "reps": s.get("reps"),
                # prs comes as {} or {"children":[...]}; only matters if it has something
                "pr": bool(s.get("prs")) and s.get("prs") != {} and s.get("prs") != {"children": []},
            })

        outputs = r.get("outputs") or []
        parent = next((o for o in outputs if o.get("complexIndex") is None), None)
        movement = parent["movement"] if parent and parent.get("movement") else None
        implied_rm, top_rm, test = block_rm(
            programmed, done, (movement or {}).get("name") or w.get("description") or "")
        parts = complex_parts(outputs, 0)

        rest = wdet.get("rest") or rdet.get("rest") or {}

        block = {
            "label": r.get("prefix"),
            "description": w.get("description"),
            "movement": ({"id": movement["id"], "name": movement["name"]}
                         if movement else None),
            "isComplex": len(parts) > 1,
            "parts": parts if len(parts) > 1 else [],
            "cadence": ({"type": rest.get("type"), "seconds": rest.get("duration")}
                        if rest else None),
            "sets": len(done) or len(programmed),
            "programmed": programmed,
            "done": done,
            "impliedRM": implied_rm,
            "impliedRMTop": top_rm,
            "maxTest": test,
            "pr": bool(r.get("pr")),
            "prKg": r.get("prAmount"),
            "notes": r.get("notes"),
            "feeling": r.get("feeling"),
            "perceivedExertion": r.get("perceivedExertion"),
            "resultId": r.get("id"),
            "workoutId": w.get("id"),
        }
        # Pre-rendered as text, so the web page and the .md files don't repeat the formatting.
        block["programmedText"] = programmed_pcts(block)
        block["doneText"] = sets_line(block)
        days[r["doneOn"]].append(block)

    return [{"date": date, "blocks": b} for date, b in sorted(days.items())]


def sets_line(block):
    """Compacts the sets: '35x6' or '23x2, 25x9, 28x4' depending on whether the weight varies."""
    groups = []
    for d in block["done"]:
        kg = d["kg"]
        if groups and groups[-1][0] == kg:
            groups[-1][1] += 1
        else:
            groups.append([kg, 1])
    return ", ".join(
        f"{kg:g} kg x{n}" if kg is not None else f"— x{n}" for kg, n in groups
    )


def programmed_pcts(block):
    seen = []
    for p in block["programmed"]:
        if p["pct"] is not None and p["pct"] not in seen:
            seen.append(p["pct"])
    return ", ".join(f"{p:g}%" for p in seen) if seen else "—"


def write_md(days, dest):
    total_blocks = sum(len(d["blocks"]) for d in days)
    out = [
        "# Training history — WodUp",
        "",
        f"{len(days)} training days · {total_blocks} blocks logged · "
        f"{days[0]['date']} → {days[-1]['date']}",
        "",
        "`implied RM` is the implied 1RM: kilos lifted ÷ programmed percentage.",
        "It is the RM actually worked with that day, which does not always match",
        "the PR shown in WodUp.",
        "",
    ]
    current_month = None
    for d in days:
        month = d["date"][:7]
        if month != current_month:
            out += ["", f"## {month}", ""]
            current_month = month
        out.append(f"### {d['date']}")
        out.append("")
        for b in d["blocks"]:
            title = b["description"] or (b["movement"] or {}).get("name") or "—"
            mark = "  ⭐ PR" if b["pr"] else ""
            out.append(f"**{b['label'] or '·'}. {title}**{mark}")
            det = [f"programmed {b['programmedText']}", f"done {b['doneText']}"]
            if b["impliedRM"]:
                det.append(f"implied RM {b['impliedRM']:g} kg")
            if b["cadence"] and b["cadence"].get("type"):
                c = b["cadence"]
                # as_needed has no duration; printing "Nones" was noise
                det.append(f"{c['type']} {c['seconds']}s" if c.get("seconds")
                           else str(c["type"]))
            out.append("- " + " · ".join(det))
            if b["isComplex"]:
                out.append("- complex: " + " + ".join(
                    f"{p['reps']} {p['name']}" for p in b["parts"]))
            if b["notes"]:
                out.append(f"- note: {b['notes']}")
            out.append("")
    open(dest, "w").write("\n".join(out))


def write_progression(days, dest):
    """One table per movement, in chronological order.

    This is the view needed to pick a weight: not the isolated PR, but which
    RM the athlete had been working with and how it moved session to session.
    Progress is not linear, so the full series says more than the max.
    """
    by_movement = defaultdict(list)
    for d in days:
        for b in d["blocks"]:
            name = (b["movement"] or {}).get("name")
            if not name:
                continue
            by_movement[name].append((d["date"], b))

    out = [
        "# Progression by movement",
        "",
        "Each row is a block, in order. `implied RM` = kilos ÷ programmed "
        "percentage.",
        "Sorted by number of sessions: most-trained movements first.",
        "",
    ]
    ordered = sorted(by_movement.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    for name, rows in ordered:
        out.append(f"## {name}  ({len(rows)} sessions)")
        out.append("")
        out.append("| Date | Programmed | Done | Implied RM | Top RM | |")
        out.append("|---|---|---|---|---|---|")
        for date, b in rows:
            out.append("| {} | {} | {} | {} | {} | {} |".format(
                date,
                b["programmedText"],
                b["doneText"] or "—",
                f"{b['impliedRM']:g}" if b["impliedRM"] else "—",
                f"{b['impliedRMTop']:g}" if b.get("impliedRMTop") else "—",
                "PR" if b["pr"] else "",
            ))
        out.append("")
    open(dest, "w").write("\n".join(out))


def main():
    res = load_results()
    if not res:
        raise SystemExit("Nothing in data/raw/. Download it from WodUp with:  make web")
    days = normalize(res)

    with open(os.path.join(DATA, "history.json"), "w") as f:
        json.dump({"source": "wodup.com", "days": days}, f, indent=2, ensure_ascii=False)

    write_md(days, os.path.join(DATA, "history.md"))
    write_progression(days, os.path.join(DATA, "progression.md"))

    print(f"{len(days)} days, {sum(len(d['blocks']) for d in days)} blocks")
    print(f"range: {days[0]['date']} → {days[-1]['date']}")


if __name__ == "__main__":
    main()
