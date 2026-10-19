import assert from 'node:assert/strict';
import * as L from './logic.mjs';
import { SEED_MAXES } from './fixtures/athlete.mjs';
let pass=0, fail=0;
const t=(n,f)=>{try{f();pass++;console.log('  ok  '+n)}catch(e){fail++;console.log('FAIL  '+n+'\n      '+e.message)}};
const mv = s => L.findMovement(s, L.ALIASES);

console.log('\n--- WodUp taxonomy ---');
t("the three clean variants don't step on each other", ()=>{
  assert.equal(mv('Clean'), 'clean');
  assert.equal(mv('Power Clean'), 'power_clean');
  assert.equal(mv('Squat Clean'), 'squat_clean');
  assert.equal(mv('Clean and Jerk'), 'clean_jerk');
});
t('nor do the three snatch variants', ()=>{
  assert.equal(mv('Snatch'), 'snatch');
  assert.equal(mv('Power Snatch'), 'power_snatch');
  assert.equal(mv('Squat Snatch'), 'squat_snatch');
});
t('push jerk / split jerk / jerk', ()=>{
  assert.equal(mv('Push Jerk'), 'push_jerk');
  assert.equal(mv('Split Jerk'), 'split_jerk');
  assert.equal(mv('Jerk 3x1 @ 90%'), 'jerk');
});
t("push press isn't mistaken for push jerk", ()=>{
  assert.equal(mv('Push Press'), 'push_press');
});
t('squats', ()=>{
  assert.equal(mv('Back Squat'), 'back_squat');
  assert.equal(mv('Front Squat'), 'front_squat');
  assert.equal(mv('Overhead Squat'), 'ohs');
});

console.log('\n--- PRs screen import ---');
const PR_OCR = `PRs & Benchmarks
Back Squat 72 kg
Front Squat 68 kg
Overhead Squat 25 kg
Clean 35 kg
Power Clean 47 kg
Squat Clean 32.5 kg
Clean and Jerk 47 kg
Snatch 33 kg
Power Snatch 30 kg
Squat Snatch 27.5 kg
Push Press 47 kg
Push Jerk 41 kg
Split Jerk 41 kg`;

t('reads the 13 PRs with their values', ()=>{
  const r = L.parsePRs(PR_OCR, L.ALIASES);
  assert.deepEqual(r, {
    back_squat:72, front_squat:68, ohs:25, clean:35, power_clean:47, squat_clean:32.5,
    clean_jerk:47, snatch:33, power_snatch:30, squat_snatch:27.5,
    push_press:47, push_jerk:41, split_jerk:41,
  });
});
t('matches the values seeded in the app', ()=>{
  assert.deepEqual(L.parsePRs(PR_OCR, L.ALIASES), SEED_MAXES);
});
t('copes with name and number on separate lines', ()=>{
  const r = L.parsePRs('Back Squat\n72 kg\nFront Squat\n68 kg', L.ALIASES);
  assert.deepEqual(r, {back_squat:72, front_squat:68});
});
t('copes with the OCR eating the kg', ()=>{
  const r = L.parsePRs('Back Squat 72\nSnatch 33', L.ALIASES);
  assert.deepEqual(r, {back_squat:72, snatch:33});
});
t('decimal comma', ()=>{
  assert.deepEqual(L.parsePRs('Squat Clean 32,5 kg', L.ALIASES), {squat_clean:32.5});
});
t('ignores the header', ()=>{
  const r = L.parsePRs(PR_OCR, L.ALIASES);
  assert.ok(!('thruster' in r));
  assert.equal(Object.keys(r).length, 13);
});

console.log('\n--- tolerance capped at 2% ---');
const ACH = L.achievablePerSide(L.DEFAULT_PLATES);
const load=(x,tol=1,mode='nearest',bar=15)=>L.bestLoad(x,bar,ACH,mode,tol);
t('a light OHS never deviates more than 2%', ()=>{
  for(const pct of [50,60,70,80,90,100]){
    const target = 25 * pct/100;
    const r = load(target, 1);
    if(!r.ok) continue;
    const exact = load(target, 0);
    const floor = Math.abs(exact.total - target);
    assert.ok(Math.abs(r.total-target) <= Math.max(floor, target*0.02) + 1e-9,
      `${pct}% of 25 -> ${r.total} (target ${target})`);
  }
});
t('on heavy loads the margin is still the one asked for', ()=>{
  const r = load(101.25, 2.5);
  assert.ok(Math.abs(r.total-101.25) <= 2.5+1e-9);
});
t('80% of a 33 snatch comes out reasonable', ()=>{
  const r = load(26.4, 1);
  assert.ok(Math.abs(r.total-26.4) <= 0.6, 'total '+r.total);
});

console.log('\n' + pass + ' ok, ' + fail + ' fail\n');
process.exit(fail?1:0);
