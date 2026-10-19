// Builds data/web.json: the week programmed in WodUp with the kilos already
// worked out, plus the per-movement history. web/index.html consumes it; the
// page is published with that file next to it as data.json.
//
// Input: data/athlete.json, data/week.json (`Week` query) and
// data/history.json + data/rms.json (make history).
// Rounding and plates come from barra.html's logic (tests/logic.mjs):
// the page and the calculator cannot disagree.
//
// The data folder can be overridden with BARRA_DATA (same variable as wodup/).

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import * as L from '../tests/logic.mjs';

const DATA_DIR = process.env.BARRA_DATA
  || path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'data');
const read = f => JSON.parse(fs.readFileSync(path.join(DATA_DIR, f), 'utf8'));
const athlete = read('athlete.json');
const { SEED_MAXES, HIST_MAXES } = read('rms.json');
const BAR = athlete.bar;
const TOL = 1;   // same default margin as barra.html
const ACH = L.achievablePerSide(L.DEFAULT_PLATES);

const week = read('week.json').data.currentUser.activityTimeline;
const hist = read('history.json').days;

// History blocks by WodUp movement id, in order.
const byMovement = new Map();
for (const day of hist) for (const b of day.blocks) {
  const id = b.movement && b.movement.id;
  if (!id) continue;
  if (!byMovement.has(id)) byMovement.set(id, { name: b.movement.name, sessions: [] });
  byMovement.get(id).sessions.push({ date: day.date, b });
}

const median = xs => [...xs].sort((a, b) => a - b)[Math.floor(xs.length / 2)];
const summary = (date, b) => ({ date, programmed: b.programmedText === '—' ? '' : b.programmedText, done: b.doneText, rm: b.impliedRM, pr: !!b.pr });

// Complexes with no history of their own: the closest family, marked as approximate.
// effectiveRM won't do: on a hang squat clean the stale Squat Clean PR would win.
const REFERENCES = [
  { test: n => n.includes('clean') && n.includes('jerk'), id: '131' },  // Squat Clean and Jerk
  { test: n => n.includes('snatch') && !n.includes('pull'), id: '52' }, // Squat Snatch
];

function medianRM(id) {
  const recent = (byMovement.get(String(id))?.sessions || []).filter(s => s.b.impliedRM).slice(-3);
  return recent.length ? { kg: median(recent.map(s => s.b.impliedRM)), values: recent.map(s => s.b.impliedRM) } : null;
}

// Where a block's RM comes from, in order:
//   1. Movement identical to one in barra.html: effectiveRM, same as the calculator.
//   2. Otherwise, the median of the last three sessions of THAT movement: it is the
//      base the coach programs it on (pulls included).
//   3. New complexes: REFERENCES. 4. Nothing: no RM, never invent one.
function blockRM(name, movId) {
  const m = L.MOVEMENTS.find(x => x.key === L.findMovement(name, L.ALIASES));
  const r = m && L.norm(m.name) === L.norm(name) && L.effectiveRM(m.key, SEED_MAXES, HIST_MAXES, {});
  if (r) return { kg: r.kg, source: r.source,
    detail: r.source === 'history' ? `implied RM as of ${r.hist.date} (${r.hist.sessions} sessions)` : 'WodUp PR' };
  const own = medianRM(movId);
  if (own) return { kg: own.kg, source: 'history', detail: `median of your last sessions (${own.values.join(', ')})` };
  const ref = REFERENCES.find(x => x.test(L.norm(name)));
  const borrowed = ref && medianRM(ref.id);
  if (borrowed) return { kg: borrowed.kg, source: 'approx',
    detail: `no history of its own: taken from your ${byMovement.get(ref.id).name}. Adjust by feel` };
  return null;
}

function load(rm, pct) {
  if (!rm || pct == null) return null;
  const target = L.pctToKg(rm.kg, pct);
  const l = L.bestLoad(target, BAR, ACH, 'nearest', TOL);
  return l.ok
    ? { target: +target.toFixed(1), kg: l.total, plates: l.plates }
    : { target: +target.toFixed(1), kg: null, plates: [], warning: l.reason === 'below-bar' ? 'below the bar' : "can't be made with your plates" };
}

// The workout name carries the scheme glued on: "Squat Snatch 1-1-1-1", "Back Squat 5 x 3".
const cleanName = n => String(n).replace(/\s+(\d+(-\d+)+|\d+\s*x\s*\d+|\d+\s+Reps?)\s*$/i, '').trim();

const days = week.flatMap(day => day.subscribedWods.map(w => ({
  date: day.date,
  name: w.name,
  blocks: w.wodComponents.filter(c => !c.hidden)
    .sort((a, b) => (a.rowOrder || 0) - (b.rowOrder || 0))
    .map((c, i) => {
      const wk = c.workout, det = wk.details || {}, movs = det.movements || [];
      const name = cleanName(wk.name || (wk.description || '').split('\n')[0]);
      const movId = movs[0]?.id;
      const rm = blockRM(name, movId);
      const last = byMovement.get(String(movId))?.sessions.at(-1);
      if (!rm && movs.some(m => m.loadUnit === '%1rm')) console.error(`WARNING ${day.date} ${name}: no RM, kilos not calculated`);
      return {
        label: c.prefix || String.fromCharCode(65 + i),
        name,
        notes: c.notes || null,
        cadence: det.rest ? { type: det.rest.type, seconds: det.rest.duration || null } : null,
        rm,
        sets: movs.map(m => {
          const pct = m.loadUnit === '%1rm' && m.load ? +m.load : null;
          return { reps: m.reps ? +m.reps : null, pct, load: load(rm, pct) };
        }),
        last: last ? summary(last.date, last.b) : null,
      };
    }),
})));

// Per-movement history: those with a % at least three times give a meaningful curve.
const lifts = [...byMovement.entries()]
  .filter(([, h]) => h.sessions.filter(s => s.b.impliedRM).length >= 3)
  .map(([id, h]) => ({
    id, name: h.name,
    sessions: h.sessions.map(({ date, b }) => ({
      ...summary(date, b), top: Math.max(0, ...b.done.map(r => r.kg || 0)) || null,
    })),
  }))
  .sort((a, b) => b.sessions.length - a.sessions.length);

const recent = hist.slice(-12).reverse().map(d => ({
  date: d.date,
  blocks: d.blocks.map(b => ({ label: b.label, name: b.movement?.name || b.description, ...summary(d.date, b) })),
}));

fs.writeFileSync(path.join(DATA_DIR, 'web.json'), JSON.stringify({
  generated: new Date().toISOString(), athlete: athlete.name, bar: BAR, plates: L.DEFAULT_PLATES, lastWorkout: hist.at(-1).date, days, lifts, recent,
}));
console.log(`${path.join(DATA_DIR, 'web.json')}: ${days.length} days, ${lifts.length} lifts with history`);
