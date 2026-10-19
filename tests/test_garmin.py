"""Checks that the JSON produced for Garmin is structurally valid."""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import garmin as G

fails = []
def t(name, fn):
    try:
        fn(); print('  ok  ' + name)
    except AssertionError as e:
        fails.append(name); print('FAIL  ' + name + '\n      ' + str(e))

def build(session, emom='time'):
    return G.build_workout(session, 'test', emom)

SES = json.loads((ROOT / 'tests/fixtures/session.json').read_text(encoding='utf-8'))

print('\n--- overall structure ---')
w, warn, notes = build(SES)

def flat(steps):
    for s in steps:
        yield s
        if s['type'] == 'RepeatGroupDTO':
            yield from flat(s['workoutSteps'])

ALL = list(flat(w['workoutSegments'][0]['workoutSteps']))

t('sportType is strength', lambda: (
    _ for _ in ()).throw(AssertionError('wrong')) if w['sportType']['sportTypeId'] != 5 else None)
t('stepOrders are unique', lambda: (
    lambda o: (_ for _ in ()).throw(AssertionError(f'duplicates: {o}')) if len(o) != len(set(o)) else None
)([s['stepOrder'] for s in ALL]))
t('stepOrders are consecutive from 1', lambda: (
    lambda o: (_ for _ in ()).throw(AssertionError(f'gaps: {sorted(o)}'))
    if sorted(o) != list(range(1, len(o)+1)) else None
)([s['stepOrder'] for s in ALL]))

def check_work_steps():
    for s in ALL:
        if s['type'] != 'ExecutableStepDTO': continue
        if s['stepType']['stepTypeKey'] == 'rest': continue
        assert 'weightValue' in s, f"step {s['stepOrder']} has no weight"
        assert s['weightValue'] > 0, f"step {s['stepOrder']} has weight 0"
        assert s['weightUnit']['unitKey'] == 'kilogram'
        assert 'category' in s, f"step {s['stepOrder']} has no category"
t('every work step has a weight in kg and a category', check_work_steps)

def check_conditions():
    for s in ALL:
        if s['type'] == 'RepeatGroupDTO':
            assert s['endCondition']['conditionTypeKey'] == 'iterations'
            assert s['endConditionValue'] == float(s['numberOfIterations'])
        else:
            k = s['endCondition']['conditionTypeKey']
            assert k in ('reps', 'time'), k
            assert s['endConditionValue'] > 0
t('end conditions are consistent', check_conditions)

print('\n--- block translation ---')
def check_emom_complex():
    g = w['workoutSegments'][0]['workoutSteps'][0]
    assert g['type'] == 'RepeatGroupDTO' and g['numberOfIterations'] == 6
    inner = g['workoutSteps']
    assert [s['stepType']['stepTypeKey'] for s in inner] == ['interval','interval','rest']
    assert inner[0]['endConditionValue'] == 1.0   # 1 Power Snatch
    assert inner[1]['endConditionValue'] == 3.0   # 3 Snatch Balances
    assert inner[0]['exerciseName'] == 'BARBELL_POWER_SNATCH'
t('A: complex -> repeat ×6 with reps per movement', check_emom_complex)

def check_emom_time():
    g = [s for s in w['workoutSegments'][0]['workoutSteps'] if s['type']=='RepeatGroupDTO'][2]
    assert g['numberOfIterations'] == 4
    step = g['workoutSteps'][0]
    assert step['endCondition']['conditionTypeKey'] == 'time'
    assert step['endConditionValue'] == 240.0
    assert step['exerciseName'] == 'BARBELL_BACK_SQUAT'
    assert step['weightValue'] == 53.0
t('C: single-movement EMOM -> 240s step with weight', check_emom_time)

def check_emom_reps_mode():
    w2, _, _ = build(SES, emom='reps')
    g = [s for s in w2['workoutSegments'][0]['workoutSteps'] if s['type']=='RepeatGroupDTO'][2]
    inner = g['workoutSteps']
    assert inner[0]['endCondition']['conditionTypeKey'] == 'reps'
    assert inner[0]['endConditionValue'] == 6.0
    assert inner[-1]['stepType']['stepTypeKey'] == 'rest'
t('--emom reps switches to rep-based steps', check_emom_reps_mode)

def check_ramp():
    steps = w['workoutSegments'][0]['workoutSteps']
    ramp = [s for s in steps if s['type']=='ExecutableStepDTO' and s.get('exerciseName')=='BARBELL_SNATCH']
    weights = [s['weightValue'] for s in ramp]
    assert weights == [28.0, 30.0, 30.5, 30.5], weights   # 4 sets, 3 weights, last one repeats
t('E: the ramp fills up to the number of sets', check_ramp)

print('\n--- warnings ---')
t('warns about the exercise missing from Garmin',
  lambda: (_ for _ in ()).throw(AssertionError(warn)) if not any('Snatch Balance' in x for x in warn) else None)
t('does not warn about the ones that exist',
  lambda: (_ for _ in ()).throw(AssertionError(warn)) if any('Back Squat' in x for x in warn) else None)
t('notes the approximate cadence of the complex',
  lambda: (_ for _ in ()).throw(AssertionError(notes)) if not any('approximate' in x for x in notes) else None)

print('\n--- edge cases ---')

def _no_raise(sess):
    try:
        build(sess); return True
    except SystemExit:
        return False

def _no_blocks():
    assert not _no_raise({'blocks': []}), 'should raise SystemExit'

def _single():
    s = {'blocks':[{'title':'Snatch','parts':[{'key':'snatch','label':'Snatch','reps':2}],
        'governing':'snatch','sets':1,'reps':2,'intervalSec':None,'restSec':None,
        'loads':[{'pct':80,'targetKg':26.4,'kg':26.5,'perSideKg':5.75,'plates':[]}]}]}
    ww,_,_ = build(s)
    st = ww['workoutSegments'][0]['workoutSteps']
    assert len(st) == 1 and st[0]['type'] == 'ExecutableStepDTO', st

def _unknown():
    s = {'blocks':[{'title':'Bar Muscle Up','parts':[{'key':None,'label':'Bar Muscle Up','reps':3}],
        'governing':None,'sets':2,'reps':3,'intervalSec':None,'restSec':60,
        'loads':[{'pct':None,'targetKg':20,'kg':20,'perSideKg':2.5,'plates':[]}]}]}
    ww, wr, _ = build(s)
    assert any('Bar Muscle Up' in x for x in wr), wr
    inner = ww['workoutSegments'][0]['workoutSteps'][0]['workoutSteps']
    assert inner[0]['category'] == 'TOTAL_BODY'
    assert 'exerciseName' not in inner[0]

def _coverage():
    import re  # noqa: PLC0415
    html = (ROOT / 'barra.html').read_text(encoding='utf-8')
    keys = set(re.findall(r"\{key:'(\w+)'", html))
    missing = keys - set(G.EXERCISES)
    assert not missing, f'unmapped: {missing}'

def _dates():
    import datetime as dt
    assert G.parse_date('today') == dt.date.today().isoformat()
    assert G.parse_date('tomorrow') == (dt.date.today()+dt.timedelta(days=1)).isoformat()
    assert G.parse_date('2026-09-01') == '2026-09-01'

def _orphan_load():
    # "4x3 @ 70kg" with no lift on the line: the 70 kg must reach the watch.
    blk = {"title": "4x3 @ 70kg", "parts": [], "governing": None, "sets": 4, "reps": 3,
           "intervalSec": None, "restSec": 60, "loads": [{"pct": None, "kg": 70}]}
    w, warn, _ = G.build_workout({"blocks": [blk]}, 'x')
    steps = list(flat(w['workoutSegments'][0]['workoutSteps']))
    work = [s for s in steps if s.get('stepType', {}).get('stepTypeKey') == 'interval']
    assert work and work[0]['weightValue'] == 70.0, steps
    assert any('4x3 @ 70kg' in x for x in warn), warn

def _name():
    n = G.default_name(SES, '2026-08-21')
    assert n.startswith('Weightlifting 2026-08-21'), n
    assert len(n) <= 80

t('no loaded blocks -> clear error', _no_blocks)
t('single set without repeat group', _single)
t('unknown movement -> generic step and warning', _unknown)
t('every movement in the app has a mapping', _coverage)
t('load with no lift keeps its weight', _orphan_load)
t('date parsing', _dates)
t('default name is short and dated', _name)

print()
print('ALL OK' if not fails else f"{len(fails)} FAILURES: {', '.join(fails)}")
sys.exit(1 if fails else 0)
