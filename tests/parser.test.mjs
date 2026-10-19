import assert from 'node:assert/strict';
import * as L from './logic.mjs';
let pass=0, fail=0;
const t=(n,f)=>{try{f();pass++;console.log('  ok  '+n)}catch(e){fail++;console.log('FAIL  '+n+'\n      '+e.message)}};
const P = txt => L.parseWod(txt, L.ALIASES);

console.log('\n--- multiline parser (real WodUp format) ---');

const OCR = `Weightlifting — Monday
Example Barbell Club - Week 4
A. Snatch

5x2 @ 80%

Rest 2:00 between sets

B. Clean & Jerk

4x1 @ 85/90/93%

Rest 2:30

C. Back Squat

3x5 @ 75%

D. Front Squat

4x3 @ 70kg`;

t('groups name and load from different lines', ()=>{
  const b = P(OCR);
  assert.equal(b.length, 4, 'blocks: '+b.length+' -> '+JSON.stringify(b.map(x=>x.movement)));
  assert.deepEqual(b.map(x=>x.movement), ['snatch','clean_jerk','back_squat','front_squat']);
});
t('loads land in the right block', ()=>{
  const b = P(OCR);
  assert.deepEqual(b[0].percents, [80]);
  assert.deepEqual(b[1].percents, [85,90,93]);
  assert.deepEqual(b[2].percents, [75]);
  assert.deepEqual(b[3].kilos, [70]);
});
t('set schemes are kept', ()=>{
  const b = P(OCR);
  assert.deepEqual(b[0].scheme, {sets:5, reps:2});
  assert.deepEqual(b[1].scheme, {sets:4, reps:1});
});
t('captures the rests', ()=>{
  const b = P(OCR);
  assert.equal(b[0].restSec, 120);
  assert.equal(b[1].restSec, 150);
  assert.equal(b[2].restSec, null);
});
t('drops header and club noise', ()=>{
  const raws = P(OCR).map(b=>b.raw).join(' ');
  assert.ok(!/Example|Week/.test(raws), raws);
});
t('strips the A. B. C. labels', ()=>{
  assert.equal(L.cleanLine('A. Snatch'), 'Snatch');
  assert.equal(L.cleanLine('B) Clean & Jerk'), 'Clean & Jerk');
  assert.equal(L.cleanLine('- Back Squat'), 'Back Squat');
  assert.equal(L.cleanLine('3) 5x2 @ 80%'), '5x2 @ 80%');
});
t("doesn't mangle normal lines", ()=>{
  assert.equal(L.cleanLine('Snatch 5x2 @ 80%'), 'Snatch 5x2 @ 80%');
  assert.equal(L.cleanLine('5x2 @ 80%'), '5x2 @ 80%');
});

console.log('\n--- rests ---');
t('mm:ss', ()=>assert.equal(L.extractRest('Rest 2:00 between sets'), 120));
t('rest in minutes, spelled out', ()=>assert.equal(L.extractRest('Rest 2 minutes'), 120));
t('rest in mins', ()=>assert.equal(L.extractRest('Rest 2 mins'), 120));
t('rest in secs', ()=>assert.equal(L.extractRest('rest 90 secs'), 90));
t('seconds', ()=>assert.equal(L.extractRest('rest 90s'), 90));
t("a line without a rest doesn't invent one", ()=>assert.equal(L.extractRest('Snatch 5x2 @ 80%'), null));

console.log('\n--- single-line format still works ---');
t('classic full line', ()=>{
  const b = P('Snatch 5x2 @ 80%\nBack Squat 3x5 @ 75%');
  assert.equal(b.length, 2);
  assert.deepEqual(b[0].percents, [80]);
  assert.deepEqual(b[1].percents, [75]);
});
t('two sets of the same movement on consecutive lines', ()=>{
  const b = P('Snatch\n5x2 @ 75%\n3x1 @ 85%');
  assert.equal(b.length, 2);
  assert.ok(b.every(x=>x.movement==='snatch'));
  assert.deepEqual(b[0].percents, [75]);
  assert.deepEqual(b[1].percents, [85]);
});
t('orphan load without a movement is flagged, not invented', ()=>{
  const b = P('5x2 @ 80%');
  assert.equal(b.length, 1);
  assert.equal(b[0].movement, null);
});
t("loose metcon text doesn't produce noise", ()=>{
  const b = P('Weightlifting\nCoach: Marta\nDay notes');
  assert.equal(b.length, 0, JSON.stringify(b));
});

console.log('\n'+pass+' ok, '+fail+' fail\n');
process.exit(fail?1:0);
