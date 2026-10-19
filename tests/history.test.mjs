import assert from 'node:assert/strict';
import * as L from './logic.mjs';
import { SEED_MAXES, HIST_MAXES } from './fixtures/athlete.mjs';
let pass=0, fail=0;
const t=(n,f)=>{try{f();pass++;console.log('  ok  '+n)}catch(e){fail++;console.log('FAIL  '+n+'\n      '+e.message)}};

// The WodUp PRs exactly as seeded.
const PR = {};
for(const m of L.MOVEMENTS) PR[m.key] = SEED_MAXES[m.key] || 0;

const H = HIST_MAXES;

console.log('\n--- where the RM comes from ---');

t('without history it behaves as it always did', ()=>{
  const rm = L.effectiveRM('front_squat', PR);
  assert.equal(rm.kg, 68);
  assert.equal(rm.source, 'pr');
});

t('history beats the PR when it is heavier', ()=>{
  const rm = L.effectiveRM('front_squat', PR, H);
  assert.equal(rm.kg, H.front_squat.kg);
  assert.equal(rm.source, 'history');
  assert.equal(rm.pr, 68);          // the stale PR stays visible so we can warn about it
  assert.ok(rm.kg > 68);
});

t('the PR wins if it is the heavier one', ()=>{
  // A fresh max single: 90 kg, above the history.
  const rm = L.effectiveRM('front_squat', Object.assign({}, PR, {front_squat:90}), H);
  assert.equal(rm.kg, 90);
  assert.equal(rm.source, 'pr');
  assert.equal(rm.hist.kg, H.front_squat.kg);   // but the history is still shown
});

t('what you type by hand wins over the history', ()=>{
  const rm = L.effectiveRM('front_squat', Object.assign({}, PR, {front_squat:60}), H, {front_squat:true});
  assert.equal(rm.kg, 60);
  assert.equal(rm.source, 'manual');
});

t("a movement without history doesn't change", ()=>{
  assert.equal(L.effectiveRM('push_press', PR, H).kg, 47);
  assert.equal(L.effectiveRM('push_press', PR, H).source, 'pr');
});

t('still returns null when there is nothing', ()=>{
  assert.equal(L.effectiveRM('bench', PR, H), null);
  assert.equal(L.effectiveRM(null, PR, H), null);
});

console.log("\n--- history doesn't break the old rules ---");

t('a borrowed RM is still marked as not exact', ()=>{
  const rm = L.effectiveRM('jerk', PR, H);
  assert.equal(rm.exact, false);
  assert.ok(['push_jerk','split_jerk'].includes(rm.from));
});

t('in a complex the weakest link still governs', ()=>{
  // "3 Front Squats + 1 Jerk": even if the history raises the front squat to 80.5,
  // the jerk is still the limiting one. If this breaks, the athlete loads too many kilos.
  const parts = [{key:'front_squat', label:'Front Squat'}, {key:'jerk', label:'Jerk'}];
  assert.equal(L.governingMovement(parts, PR, H), 'jerk');
  const rm = L.effectiveRM('jerk', PR, H);
  assert.ok(rm.kg < L.effectiveRM('front_squat', PR, H).kg);
});

t('raising an RM from history never moves governance to the heavier one', ()=>{
  // For every pair in the complex, the governing one must still be the one
  // with the lowest effective RM, with or without history.
  const keys = L.MOVEMENTS.map(m => m.key).filter(k => L.effectiveRM(k, PR, H));
  for(const a of keys){
    for(const b of keys){
      if(a === b) continue;
      const gov = L.governingMovement([{key:a},{key:b}], PR, H);
      const ra = L.effectiveRM(a, PR, H).kg, rb = L.effectiveRM(b, PR, H).kg;
      assert.equal(L.effectiveRM(gov, PR, H).kg, Math.min(ra, rb));
    }
  }
});

console.log('\n--- a lift picked by hand in a complex ---');
const FS_JERK = [{key:'front_squat'}, {key:'jerk'}];
t('a valid pick wins over the weakest link', ()=>{
  assert.equal(L.governingFor(FS_JERK, 'front_squat', PR), 'front_squat');
});
t("a pick that isn't in the block is ignored", ()=>{
  // It used to stick to the block position: the next workout's Snatch came
  // out of the Front Squat RM.
  assert.equal(L.governingFor([{key:'snatch'}], 'front_squat', PR), 'snatch');
});
t('a pick without an RM falls back to the weakest link', ()=>{
  assert.equal(L.governingFor([{key:'snatch'}, {key:'rdl'}], 'rdl', PR), 'snatch');
});

console.log(`\n${pass} ok, ${fail} fail`);
process.exit(fail ? 1 : 0);
