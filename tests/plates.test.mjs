import assert from 'node:assert/strict';
import * as L from './logic.mjs';

let pass = 0, fail = 0;
const t = (name, fn) => {
  try { fn(); pass++; console.log('  ok  ' + name); }
  catch (e) { fail++; console.log('FAIL  ' + name + '\n      ' + e.message); }
};

const PL = L.DEFAULT_PLATES;
const ACH = L.achievablePerSide(PL);
const load = (target, bar = 15, mode = 'nearest') => L.bestLoad(target, bar, ACH, mode);

console.log('\n--- plate solver ---');

t('empty bar', () => {
  const r = load(15);
  assert.equal(r.total, 15);
  assert.deepEqual(r.plates, []);
});

t('60 kg on a 15 bar = 22.5/side', () => {
  const r = load(60);
  assert.equal(r.total, 60);
  assert.equal(r.perSide, 22.5);
  assert.equal(r.delta, 0);
});

t('100 kg on a 20 bar', () => {
  const r = load(100, 20);
  assert.equal(r.total, 100);
  assert.equal(r.perSide, 40);
});

t('uses the big plates first', () => {
  const r = load(115, 15); // 50/side
  assert.equal(r.total, 115);
  assert.equal(r.plates[0].w, 25);
  assert.equal(r.plates[0].n, 2);
});

t('82.3 kg rounds to the nearest loadable', () => {
  const r = load(82.3);
  assert.ok(Math.abs(r.delta) <= 0.5, 'delta ' + r.delta);
  assert.ok(r.total >= 82 && r.total <= 82.6, 'total ' + r.total);
});

t('down mode never goes over the target', () => {
  for (const target of [61.3, 82.7, 97.9, 143.2]) {
    const r = load(target, 15, 'down');
    assert.ok(r.total <= target + 1e-9, target + ' -> ' + r.total);
  }
});

t('up mode never falls short', () => {
  for (const target of [61.3, 82.7, 97.9, 143.2]) {
    const r = load(target, 15, 'up');
    assert.ok(r.total >= target - 1e-9, target + ' -> ' + r.total);
  }
});

t('below the bar is flagged', () => {
  const r = load(12);
  assert.equal(r.ok, false);
  assert.equal(r.reason, 'below-bar');
});

t('respects the inventory: without 2.5s there are no fine 5 kg jumps', () => {
  const only = L.achievablePerSide([{ w: 20, pairs: 2 }, { w: 10, pairs: 1 }]);
  const r = L.bestLoad(63, 15, only, 'nearest');
  // only 15, 35, 55, 75, 95... can be loaded
  assert.ok([55, 75].includes(r.total), 'total ' + r.total);
});

t('never uses more pairs than available', () => {
  const inv = [{ w: 25, pairs: 2 }, { w: 20, pairs: 2 }];
  const a = L.achievablePerSide(inv);
  for (const [, combo] of a) {
    for (const p of combo) {
      const max = inv.find(x => x.w === p.w).pairs;
      assert.ok(p.n <= max, p.w + 'kg x' + p.n + ' > ' + max);
    }
  }
});

t('the total always matches the breakdown', () => {
  for (const target of [40, 57.5, 83.4, 121, 160.6]) {
    const r = load(target);
    if (!r.ok) continue;
    const sum = r.plates.reduce((s, p) => s + p.w * p.n, 0);
    assert.ok(Math.abs(sum - r.perSide) < 1e-9, 'perSide ' + r.perSide + ' vs ' + sum);
    assert.ok(Math.abs(r.bar + sum * 2 - r.total) < 1e-9, 'total ' + r.total);
  }
});

console.log('\n--- movement detection ---');

const mv = s => L.findMovement(s, L.ALIASES);

t("power clean doesn't get swallowed by clean", () => assert.equal(mv('Power Clean 5x3 @ 70%'), 'power_clean'));
t('plain clean', () => assert.equal(mv('Clean 3x2 @ 80%'), 'clean'));
t('clean and jerk', () => assert.equal(mv('Clean and Jerk 4x1 @ 85%'), 'clean_jerk'));
t('abbreviated c&j', () => assert.equal(mv('C&J 4x1 @ 85%'), 'clean_jerk'));
t('front squat vs back squat', () => {
  assert.equal(mv('Front Squat 4x3'), 'front_squat');
  assert.equal(mv('Back Squat 5x5'), 'back_squat');
});
t('hang snatch falls into snatch', () => assert.equal(mv('Hang Snatch 3x2 @ 75%'), 'snatch'));
t('power snatch has its own', () => assert.equal(mv('Power snatch 5x2'), 'power_snatch'));
t('line without a movement returns null', () => assert.equal(mv('20 min EMOM cardio'), null));
t("doesn't match a loose substring", () => assert.equal(mv('cleaning the bar'), null));

console.log('\n--- parser ---');

t('simple scheme and percentage', () => {
  const [b] = L.parseWod('Snatch 5x2 @ 80%', L.ALIASES);
  assert.equal(b.movement, 'snatch');
  assert.deepEqual(b.scheme, { sets: 5, reps: 2 });
  assert.deepEqual(b.percents, [80]);
});

t('ramping percentages', () => {
  const [b] = L.parseWod('Clean & Jerk 4x1 @ 85/87.5/90%', L.ALIASES);
  assert.deepEqual(b.percents, [85, 87.5, 90]);
  assert.equal(b.movement, 'clean_jerk');
});

t('comma-separated percentages', () => {
  const [b] = L.parseWod('Back squat 3x5 @ 70%, 75%, 80%', L.ALIASES);
  assert.deepEqual(b.percents, [70, 75, 80]);
});

t('absolute kilos', () => {
  const [b] = L.parseWod('Front squat 4x3 @ 70kg', L.ALIASES);
  assert.deepEqual(b.kilos, [70]);
  assert.deepEqual(b.percents, []);
});

t('if there is a % the kg are ignored', () => {
  const [b] = L.parseWod('Snatch 5x2 @ 80% (RM 90kg)', L.ALIASES);
  assert.deepEqual(b.percents, [80]);
  assert.deepEqual(b.kilos, []);
});

t('decimal comma', () => {
  const [b] = L.parseWod('Snatch 3x2 @ 82,5%', L.ALIASES);
  assert.deepEqual(b.percents, [82.5]);
});

t('strips bullets and numbering', () => {
  const bs = L.parseWod('- Snatch 5x2 @ 80%\n2) Back Squat 3x5 @ 75%\n\n• Jerk 2x2 @ 90%', L.ALIASES);
  assert.equal(bs.length, 3);
  assert.equal(bs[0].movement, 'snatch');
  assert.equal(bs[1].movement, 'back_squat');
  assert.equal(bs[2].movement, 'jerk');
});

t('uppercase X and the times symbol', () => {
  assert.deepEqual(L.extractSetsReps('Snatch 5X2'), { sets: 5, reps: 2 });
  assert.deepEqual(L.extractSetsReps('Snatch 5×2'), { sets: 5, reps: 2 });
});

t("a metcon line doesn't break anything", () => {
  const [b] = L.parseWod('21-15-9 thrusters and pullups', L.ALIASES);
  assert.equal(b.movement, 'thruster');
  assert.deepEqual(b.percents, []);
});

console.log('\n--- real end-to-end case ---');

t('full session with RMs of 90/110/140', () => {
  const maxes = { snatch: 90, clean_jerk: 110, back_squat: 140 };
  const wod = 'Snatch 5x2 @ 80%\nClean & Jerk 4x1 @ 85/90%\nBack Squat 3x5 @ 75%';
  const out = L.parseWod(wod, L.ALIASES).map(b => {
    const max = maxes[b.movement];
    return b.percents.map(p => load(L.pctToKg(max, p)).total);
  });
  assert.deepEqual(out[0], [72]);            // 80% of 90 = 72
  assert.deepEqual(out[1], [93.5, 99]);      // 85% and 90% of 110 = 93.5 / 99
  assert.deepEqual(out[2], [105]);           // 75% of 140 = 105
});

console.log('\n' + pass + ' ok, ' + fail + ' fail\n');
process.exit(fail ? 1 : 0);
