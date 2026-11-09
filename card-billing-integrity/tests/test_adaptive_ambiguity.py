"""Fixed counterexample and denominator checks for the adaptive metric."""
from copy import deepcopy
import json
from pathlib import Path
from adaptive_ambiguity import ambiguous, candidates, evaluate

led={1:dict(m=0,amt=4,st='C',cum=2,ev=[(1,False),(1,False),(2,True)])}
F=(0,[(20,1,1)])
snapshot=deepcopy(led)
assert ambiguous(led,0)
r=evaluate([(led,F,[],{})],(0,0,1))
assert r['counts']['accepted_originals']==1
assert r['counts']['selectable_originals']==1
assert any(v['modified']==(0,[]) for v in r['examples'])
assert led==snapshot
assert evaluate([(led,(0,[]),[],{})],(0,0,1))['counts'].get('accepted_originals',0)==0
unique={1:dict(m=0,amt=4,st='C',cum=2,ev=[(1,False),(2,True)])}
assert not ambiguous(unique,0)
equal={1:dict(m=0,amt=4,st='C',cum=1,ev=[(1,False),(1,True)])}
assert not ambiguous(equal,0) # interchangeable events, identical residual multiset
ops=list(candidates((0,[(20,1,1),(20,1,1)]),led))
assert sum(k=='cancellation deletion' for k,_ in ops)==1
old=json.loads(Path('results/review_v4/s5_ambiguity.json').read_text())
new=json.loads(Path('results/review_v5/adaptive_ambiguity.json').read_text())
for v in new:
 base=next(a for a in old if all(a[k]==v[k] for k in ('p','pi','cc')))
 assert v['counts']['accepted_originals']==1000-base['counts']['무변조 거절 X2']
 assert len(set(v['witness_original_indices']))==v['counts'].get('selectable_originals',0)
print('OK: fixed counterexample, rejected-original exclusion, residual ambiguity, multiset deduplication, immutable ledger, 32 original-acceptance denominators, unique witness indices')
