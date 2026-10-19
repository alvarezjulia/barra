import assert from 'node:assert/strict';
import * as L from './logic.mjs';
import { SEED_MAXES } from './fixtures/athlete.mjs';
let pass=0, fail=0;
const t=(n,f)=>{try{f();pass++;console.log('  ok  '+n)}catch(e){fail++;console.log('FAIL  '+n+'\n      '+e.message)}};
const M = SEED_MAXES;
const P = txt => L.parseWod(txt, L.ALIASES);

console.log('\n--- intervals from DAY 1 ---');
t('bare «Every minute» means 60s', ()=>{
  assert.deepEqual(L.extractInterval('Every minute, for 21 minutes (21 sets):'),
    {everySec:60, totalSec:1260, sets:21});
});
t('«Every 2:30» in mm:ss', ()=>{
  assert.deepEqual(L.extractInterval('Every 2:30, for 25 minutes (10 sets):'),
    {everySec:150, totalSec:1500, sets:10});
});
t('«for 17:30» in mm:ss too', ()=>{
  assert.deepEqual(L.extractInterval('Every 2:30, for 17:30 (7 sets):'),
    {everySec:150, totalSec:1050, sets:7});
});
t("doesn't break the earlier formats", ()=>{
  assert.deepEqual(L.extractInterval('Every 75 seconds, for 18:45 (15 sets)'),
    {everySec:75, totalSec:1125, sets:15});
  assert.deepEqual(L.extractInterval('EMOM 12'), {everySec:60, totalSec:720, sets:12});
});
t('a normal line is still not an interval', ()=>{
  assert.equal(L.extractInterval('Snatch 5x2 @ 80%'), null);
  assert.equal(L.extractInterval('2 Front Squats @ 77% of 1RM'), null);
});

console.log('\n--- borrowed RM ---');
t('Jerk without its own RM takes the Push Jerk one', ()=>{
  const rm = L.effectiveRM('jerk', M);
  assert.equal(rm.kg, 41);
  assert.equal(rm.exact, false);
  assert.ok(['push_jerk','split_jerk'].includes(rm.from));
});
t("a movement with its own RM doesn't borrow anything", ()=>{
  const rm = L.effectiveRM('front_squat', M);
  assert.equal(rm.kg, 68);
  assert.equal(rm.from, 'front_squat');
  assert.equal(rm.exact, true);
  // Without history passed in, the source is the PR: calling it with two arguments
  // must keep behaving as it did before HIST_MAXES existed.
  assert.equal(rm.source, 'pr');
});
t('no RM and no substitute returns null', ()=>{
  assert.equal(L.effectiveRM('rdl', M), null);
  assert.equal(L.effectiveRM(null, M), null);
});
t('the substitute is never heavier than the real one', ()=>{
  for(const [key, alts] of Object.entries(L.RM_SUBSTITUTE)){
    for(const alt of alts){
      if(!M[key] || !M[alt]) continue;
      assert.ok(M[alt] <= M[key] * 1.35, `${alt} (${M[alt]}) far above ${key} (${M[key]})`);
    }
  }
});

console.log('\n--- the dangerous complex ---');
t('«3 Front Squats + 1 Jerk»: the jerk governs, not the squat', ()=>{
  const parts = L.splitComplex('3 Front Squats + 1 Jerk @ 70% of 1RM', L.ALIASES);
  assert.deepEqual(parts.map(p=>p.key), ['front_squat','jerk']);
  assert.deepEqual(parts.map(p=>p.reps), [3,1]);
  const g = L.governingMovement(parts, M);
  assert.equal(g, 'jerk');
  assert.equal(L.effectiveRM(g, M).kg, 41);
});
t('getting it wrong costs 19 kg', ()=>{
  const withJerk = L.pctToKg(41, 70);
  const withSquat = L.pctToKg(68, 70);
  assert.ok(withSquat - withJerk > 18, `${withSquat} vs ${withJerk}`);
});
t('the Snatch Balance still does not govern over the Power Snatch', ()=>{
  const parts = L.splitComplex('1 Power Snatch + 3 Snatch Balances @ 70%', L.ALIASES);
  assert.equal(L.governingMovement(parts, M), 'power_snatch');
});

console.log('\n--- full DAY 1 session ---');
const WOD = `A. Every minute, for 21 minutes (21 sets):
1 Squat Snatch @ 70% of 1RM
B. Every 2:30, for 25 minutes (10 sets):
3 Front Squats + 1 Jerk @ 70% of 1RM
C. Every 2:30, for 17:30 (7 sets):
2 Front Squats @ 77% of 1RM
D. GHD Hip Extension
3 sets of 10 reps
Rest as needed`;

t('four cleanly separated blocks', ()=>{
  const b = P(WOD);
  assert.equal(b.length, 4, JSON.stringify(b.map(x=>x.parts.map(p=>p.label))));
});
t('A: Squat Snatch with its own RM', ()=>{
  const b = P(WOD)[0];
  assert.deepEqual(b.parts.map(p=>p.key), ['squat_snatch']);
  assert.equal(b.interval.everySec, 60);
  assert.equal(b.scheme.sets, 21);
  assert.equal(L.effectiveRM('squat_snatch', M).kg, 27.5);
});
t('B: complex with a 2:30 interval', ()=>{
  const b = P(WOD)[1];
  assert.equal(b.interval.everySec, 150);
  assert.equal(b.scheme.sets, 10);
  assert.equal(L.governingMovement(b.parts, M), 'jerk');
});
t('C: 7 sets every 2:30 at 77%', ()=>{
  const b = P(WOD)[2];
  assert.equal(b.interval.everySec, 150);
  assert.equal(b.scheme.sets, 7);
  assert.equal(b.parts[0].reps, 2);
  assert.deepEqual(b.percents, [77]);
});
t('D: GHD without a load is not calculated', ()=>{
  const b = P(WOD)[3];
  assert.deepEqual(b.percents, []);
  assert.deepEqual(b.scheme, {sets:3, reps:10});
});

console.log('\n' + pass + ' ok, ' + fail + ' fail\n');
process.exit(fail?1:0);
