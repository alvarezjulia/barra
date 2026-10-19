import assert from 'node:assert/strict';
import * as L from './logic.mjs';
import { SEED_MAXES } from './fixtures/athlete.mjs';
let pass=0, fail=0;
const t=(n,f)=>{try{f();pass++;console.log('  ok  '+n)}catch(e){fail++;console.log('FAIL  '+n+'\n      '+e.message)}};
const P = txt => L.parseWod(txt, L.ALIASES);
const M = SEED_MAXES;

// The real session, exactly as it would come out of the screenshot (with the UI noise)
const WOD = `Strength and Conditioning
Log Result Leaderboard
DAY 2 W2/12
A. Every 2 minutes, for 12 minutes (6 sets):
1 Power Snatch + 3 Snatch Balances @ 70% of 1RM
B. Every 2 minutes, for 12 minutes (6 sets):
Power Clean + Push Jerk + Split Jerk @ 70% of 1RM
C. Every 4 minutes, for 16 minutes (4 sets):
6 Back Squats @ 74% of 1RM
D. Romanian Deadlift
3 sets of 10 reps @ 50% of 1RM
Rest as needed
Show less`;

console.log('\n--- the real WodUp session ---');
const B = P(WOD);

t('exactly 4 blocks come out', ()=>{
  assert.equal(B.length, 4, B.map(b=>b.parts.map(p=>p.label).join('+')).join(' | '));
});
t('drops the UI noise', ()=>{
  const raws = B.map(b=>b.raw).join(' ');
  assert.ok(!/Log Result|Leaderboard|Show less|DAY 2/.test(raws), raws);
});

t('A: two-movement complex with its reps', ()=>{
  const a = B[0];
  assert.deepEqual(a.parts.map(p=>p.key), ['power_snatch','snatch_balance']);
  assert.deepEqual(a.parts.map(p=>p.reps), [1,3]);
  assert.deepEqual(a.percents, [70]);
});
t('A: the EMOM header sticks to the block', ()=>{
  assert.deepEqual(B[0].interval, {everySec:120, totalSec:720, sets:6});
  assert.equal(B[0].scheme.sets, 6);
});
t('A: the Power Snatch governs (the Snatch Balance has no RM)', ()=>{
  assert.equal(L.governingMovement(B[0].parts, M), 'power_snatch');
});

t('B: three-jerk complex', ()=>{
  assert.deepEqual(B[1].parts.map(p=>p.key), ['power_clean','push_jerk','split_jerk']);
  assert.deepEqual(B[1].percents, [70]);
});
t('B: the weakest link governs, not the clean', ()=>{
  const g = L.governingMovement(B[1].parts, M);
  assert.ok(g === 'push_jerk' || g === 'split_jerk', 'governs '+g);
  assert.equal(M[g], 41);
});

t('C: reps before the movement + sets from the header', ()=>{
  const c = B[2];
  assert.deepEqual(c.parts.map(p=>p.key), ['back_squat']);
  assert.equal(c.parts[0].reps, 6);
  assert.equal(c.scheme.sets, 4);
  assert.equal(c.scheme.reps, 6);
  assert.deepEqual(c.percents, [74]);
  assert.deepEqual(c.interval, {everySec:240, totalSec:960, sets:4});
});

t('D: "3 sets of 10 reps" on the line below', ()=>{
  const d = B[3];
  assert.deepEqual(d.parts.map(p=>p.key), ['rdl']);
  assert.deepEqual(d.scheme, {sets:3, reps:10});
  assert.deepEqual(d.percents, [50]);
});
t('D: "Rest as needed" does not invent a rest', ()=>{
  assert.equal(B[3].restSec, null);
});
t('D: without an RDL RM nothing is calculated blindly', ()=>{
  assert.equal(L.governingMovement(B[3].parts, M), null);
});

console.log('\n--- weights her PRs would give ---');
const ACH = L.achievablePerSide(L.DEFAULT_PLATES);
const kg = (pct, key) => L.bestLoad(L.pctToKg(M[key], pct), 15, ACH, 'nearest', 1).total;
t('A: 70% of Power Snatch 30 = 21 kg', ()=>assert.equal(kg(70,'power_snatch'), 21));
t('B: 70% of 41 ~ 28.5 kg', ()=>{
  const v = kg(70,'push_jerk');
  assert.ok(Math.abs(v-28.7)<=0.6, 'got '+v);
});
t('C: 74% of Back Squat 72 ~ 53 kg', ()=>{
  const v = kg(74,'back_squat');
  assert.ok(Math.abs(v-53.28)<=1.1, 'got '+v);
});

console.log('\n--- intervals ---');
t('every N minutes for M minutes (K sets)', ()=>{
  assert.deepEqual(L.extractInterval('Every 2 minutes, for 12 minutes (6 sets)'),
    {everySec:120, totalSec:720, sets:6});
});
t('infers the sets if not given', ()=>{
  assert.deepEqual(L.extractInterval('Every 90 seconds for 15 minutes'),
    {everySec:90, totalSec:900, sets:10});
});
t('EMOM', ()=>{
  assert.deepEqual(L.extractInterval('EMOM 12'), {everySec:60, totalSec:720, sets:12});
});
t('a normal line is not an interval', ()=>{
  assert.equal(L.extractInterval('Snatch 5x2 @ 80%'), null);
});

console.log('\n--- sets and reps in all their forms ---');
t('5x2', ()=>assert.deepEqual(L.extractSetsReps('Snatch 5x2 @ 80%'), {sets:5, reps:2}));
t('3 sets of 10 reps', ()=>assert.deepEqual(L.extractSetsReps('3 sets of 10 reps @ 50%'), {sets:3, reps:10}));
t('only (6 sets)', ()=>assert.deepEqual(L.extractSetsReps('(6 sets)'), {sets:6}));
t('nothing at all', ()=>assert.equal(L.extractSetsReps('Romanian Deadlift'), null));

console.log('\n--- complexes ---');
t("a part without an RM doesn't drag the calculation", ()=>{
  const parts = L.splitComplex('1 Power Snatch + 3 Snatch Balances @ 70%', L.ALIASES);
  assert.equal(parts.length, 2);
  assert.equal(L.governingMovement(parts, {power_snatch:30}), 'power_snatch');
});
t('an unknown movement keeps its name', ()=>{
  const parts = L.splitComplex('2 Bar Muscle Ups + 3 Thrusters', L.ALIASES);
  assert.equal(parts.length, 2);
  assert.ok(parts.some(p=>p.key==='thruster'));
  assert.ok(parts.some(p=>p.key===null && /muscle up/i.test(p.label)), JSON.stringify(parts));
});
t('"1RM" does not sneak in as reps', ()=>{
  const parts = L.splitComplex('Power Clean + Push Jerk @ 70% of 1RM', L.ALIASES);
  assert.deepEqual(parts.map(p=>p.key), ['power_clean','push_jerk']);
  assert.deepEqual(parts.map(p=>p.reps), [null,null]);
});
t('plurals', ()=>{
  assert.equal(L.findMovement('6 Back Squats', L.ALIASES), 'back_squat');
  assert.equal(L.findMovement('3 Snatch Balances', L.ALIASES), 'snatch_balance');
});

console.log('\n' + pass + ' ok, ' + fail + ' fail\n');
process.exit(fail?1:0);
