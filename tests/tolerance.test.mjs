import assert from 'node:assert/strict';
import * as L from './logic.mjs';
let pass=0, fail=0;
const t=(n,f)=>{try{f();pass++;console.log('  ok  '+n)}catch(e){fail++;console.log('FAIL  '+n+'\n      '+e.message)}};
const ACH = L.achievablePerSide(L.DEFAULT_PLATES);
const load=(target,tol=1,mode='nearest',bar=15)=>L.bestLoad(target,bar,ACH,mode,tol);

console.log('\n--- tolerance / fewer plates ---');
t('tol 0 hits the weight exactly', ()=>{
  const r=load(65.6,0);
  assert.equal(r.total,65.5);
});
t('tol 1 simplifies 40% of 82', ()=>{
  const r=load(32.8,1);
  assert.ok(Math.abs(r.total-32.8)<=1+1e-9, 'total '+r.total);
  assert.ok(L.plateCount(r.plates) <= L.plateCount(load(32.8,0).plates), "doesn't simplify");
});
t('the 2% cap protects light loads', ()=>{
  // 32.8 kg with tol 2.5 can NOT drift to 30 or 35: the effective margin is 0.66 kg
  const r=load(32.8,2.5);
  assert.ok(Math.abs(r.total-32.8)<=32.8*0.02+1e-9, 'total '+r.total);
});
t('tol 2.5 does simplify when the load is heavy', ()=>{
  const r=load(128.4,2.5);
  assert.ok(Math.abs(r.total-128.4)<=2.5+1e-9);
  assert.ok(L.plateCount(r.plates)<=L.plateCount(load(128.4,0).plates));
});
t('never exceeds the promised margin', ()=>{
  for(const tol of [0,0.5,1,2.5]){
    for(let x=20; x<=200; x+=1.7){
      const r=load(x,tol);
      if(!r.ok) continue;
      const exact=load(x,0);
      const floor=Math.abs(exact.total-x);
      const eff=Math.min(tol, x*0.02);
      assert.ok(Math.abs(r.total-x) <= Math.max(floor,eff)+1e-9, `tol ${tol} target ${x} -> ${r.total}`);
    }
  }
});
t('tolerance respects down mode', ()=>{
  for(let x=30;x<=180;x+=3.3){
    const r=load(x,2.5,'down');
    assert.ok(r.total<=x+1e-9, x+' -> '+r.total);
  }
});
t('more tolerance never uses more plates', ()=>{
  for(let x=25;x<=180;x+=2.1){
    const a=L.plateCount(load(x,0).plates);
    const b=L.plateCount(load(x,1).plates);
    const c=L.plateCount(load(x,2.5).plates);
    assert.ok(b<=a && c<=b, `x=${x} ${a}/${b}/${c}`);
  }
});
t('the breakdown still adds up with tolerance', ()=>{
  for(let x=25;x<=200;x+=4.3){
    const r=load(x,2.5);
    const sum=r.plates.reduce((s,p)=>s+p.w*p.n,0);
    assert.ok(Math.abs(r.bar+sum*2-r.total)<1e-9);
  }
});
console.log('\n'+pass+' ok, '+fail+' fail\n');
process.exit(fail?1:0);
