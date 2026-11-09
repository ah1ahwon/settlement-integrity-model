"""Original-file-level selection in a finite cancellation attack family.

The attacker knows its own authorization/reflection history and A, but changes
only F. This measures existence of a distinguishing candidate, not unrestricted
optimality, black-box attack performance, or population incidence.
"""
import argparse
import json
from collections import Counter
from itertools import product
from pathlib import Path
from ref3 import ref_accept
from s5_ambiguity import build, KX, KY, PIS, PS, CCS


def ambiguous(led, merchant):
    for v in led.values():
        if v['m'] != merchant or v['st'] != 'C':
            continue
        events = [a for a, _ in v['ev']]
        residuals = set()
        for bits in product((0, 1), repeat=len(events)):
            if sum(a*b for a, b in zip(events, bits)) == v['cum']:
                residuals.add(tuple(sorted(a for a, b in zip(events, bits) if not b)))
        if len(residuals) > 1:
            return True
    return False


def candidates(F, led):
    merchant, records = F
    seen = set()
    for i, rec in enumerate(records):
        if rec[0] == 20:
            trial = records[:i] + records[i+1:]
            key = tuple(sorted(trial))
            if key not in seen:
                seen.add(key)
                yield 'cancellation deletion', (merchant, trial)
    for k, v in sorted(led.items()):
        if v['m'] == merchant and v['st'] == 'C':
            for amount in sorted({a for a, _ in v['ev']}):
                trial = records + [(20, k, amount)]
                key = tuple(sorted(trial))
                if key not in seen:
                    seen.add(key)
                    yield 'approved-amount insertion', (merchant, trial)


def evaluate(cases, A):
    counts = Counter(); examples = []; witnesses = []
    for idx, (led, F, _, _) in enumerate(cases):
        if not ref_accept(F, led, KY, A):
            continue
        assert ref_accept(F, led, KX, A)
        amb = ambiguous(led, F[0])
        counts['accepted_originals'] += 1
        counts['ambiguous_accepted_originals'] += amb
        found = None
        for kind, G in candidates(F, led):
            counts['candidate_checks'] += 1
            x, y = ref_accept(G, led, KX, A), ref_accept(G, led, KY, A)
            assert x or not y
            if x and not y:
                counts['successful_candidates'] += 1
                counts['successful_' + kind] += 1
                if found is None:
                    found = dict(original_index=idx, kind=kind, original=F, modified=G)
        if found:
            assert amb, 'No amount-level distinction without residual ambiguity'
            counts['selectable_originals'] += 1
            witnesses.append(found)
            if len(examples) < 2:
                examples.append(found)
    n=counts['accepted_originals'];a=counts['ambiguous_accepted_originals'];s=counts['selectable_originals']
    return dict(counts=dict(counts), selectable_all_percent=100*s/n if n else None,
                selectable_ambiguous_percent=100*s/a if a else None, examples=examples,
                witness_original_indices=[v['original_index'] for v in witnesses])


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',required=True);args=ap.parse_args()
    results=[]
    print('seed=2024; 1000 originals per p,pi; CR=2; cs=3; amount-level; own reflection known')
    print('Candidates: one cancellation deletion or one approved-amount C-state insertion')
    for p in PS:
        for pi in PIS:
            cases=build(pi,p)
            for cc in CCS:
                result=evaluate(cases,(2,3,cc));c=result['counts'];n=c.get('accepted_originals',0);a=c.get('ambiguous_accepted_originals',0);s=c.get('selectable_originals',0)
                result.update(p=p,pi=pi,cc=cc,seed=2024)
                results.append(result)
                rate=lambda v:'NA' if v is None else f'{v:.2f}%'
                print(f'p={p} pi={pi} cc={cc}: selectable/all={s}/{n} ({rate(result["selectable_all_percent"])}); selectable/ambiguous={s}/{a} ({rate(result["selectable_ambiguous_percent"])}); checks={c["candidate_checks"]}')
    Path(args.output).write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
    print('All witnesses satisfy X1+Z accept / X2 reject; none outside structural ambiguity.')


if __name__=='__main__':
    main()
