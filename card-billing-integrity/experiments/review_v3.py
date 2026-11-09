"""Review additions. Run with PYTHONPATH=src:tests:experiments:legacy.

Synthetic controls are selected scenarios, not prevalence estimates.
The source-file cluster bootstrap resamples complete original files.
"""
import argparse
import copy
import itertools
import json
import platform
import random
import statistics
import time
from collections import defaultdict
from pathlib import Path
from run9 import make_case5
from m4 import attacks4
from ref2 import ref_accept as old
from ref3 import ref_accept, ref_accept_id


def controlled():
    rows = []
    # Only the last event amount changes. Event count, true flags, file,
    # allowance and transaction state remain fixed.
    for q, last, cc, sent in itertools.product((1, 2, 5), (2, 3), range(4), ((), (0,), (2,))):
        vals = [q, q, last*q]
        led = {1: dict(m=0, amt=10*q, st='C', cum=vals[2],
                       ev=[(a, j == 2) for j, a in enumerate(vals)])}
        F = (0, [(20, 1, vals[j]) for j in sent])
        r = [ref_accept(F, led, set(k), (0, 0, cc)) for k in ('LDBZX', 'LDBZY')]
        rows.append(dict(scale=q, last=last, cc=cc, sent=list(sent), X1=r[0], X2=r[1]))
    # Two ambiguous transactions: each individually fits cc=3 under both
    # levels, but their true minimum costs add to four.
    led = {i: dict(m=0, amt=4, st='C', cum=2,
                  ev=[(1, False), (1, False), (2, True)]) for i in (1, 2)}
    coupling = []
    for cc in range(5):
        full = [ref_accept((0, []), led, set(k), (0, 0, cc)) for k in ('LDBZX', 'LDBZY')]
        individual = [all(ref_accept((0, []), {i: led[i]}, set(k), (0, 0, cc)) for i in led)
                      for k in ('LDBZX', 'LDBZY')]
        coupling.append(dict(cc=cc, full=full, individual=individual))
    # Valid IDs alone add no discrimination for the amount collision;
    # known reflection flags distinguish replay of event 1 from event 0.
    ident = {1: dict(m=0, amt=3, st='C', cum=1, ev=[(1, False), (1, True)])}
    id_result = dict(amount=ref_accept((0, [(20, 1, 1)]), ident, set('LDBZY'), (0, 0, 0)),
                     event_id=ref_accept_id((0, [(20, 1, 1, 1)]), ident, set('LDBZY'), (0, 0, 0)))
    return dict(single_factor=rows, coupling=coupling, id_replay=id_result)


def a5_control():
    rows = []
    # Fully observed, single U transaction. Alternative A5 charges pending
    # cancellations even when the sale is deferred; all other rules fixed.
    # Direct enumeration has only one state and no reflected events.
    for n, cs, cc, send_sale in itertools.product(range(6), range(2), range(5), (False, True)):
        led = {1: dict(m=0, amt=10, st='U', cum=0, ev=[(1, False)]*n)}
        F = (0, [(10, 1, 10)] if send_sale else [])
        baseline = ref_accept(F, led, set('LDBZY'), (0, cs, cc))
        sale_cost = 0 if send_sale else 1
        expected = sale_cost <= cs and (n if send_sale else 0) <= cc
        alternative = sale_cost <= cs and n <= cc
        assert baseline == expected
        rows.append(dict(n=n, cs=cs, cc=cc, sent=send_sale,
                         A5=baseline, count_all_pending=alternative))
    return dict(cases=len(rows), different=sum(r['A5'] != r['count_all_pending'] for r in rows), rows=rows)


def bootstrap(clusters, repeats=2000):
    # Each row: (rejected sale deletes, total sale deletes,
    #            rejected cancel deletes, total cancel deletes).
    rng = random.Random(9162026)
    draws = [[], []]
    for _ in range(repeats):
        s = [0]*4
        for j in rng.choices(range(len(clusters)), k=len(clusters)):
            x = clusters[j]
            for k in range(4): s[k] += x[k]
        for k in range(2):
            if s[2*k+1]: draws[k].append(100*s[2*k]/s[2*k+1])
    def percentile(v, q):
        v = sorted(v); p = (len(v)-1)*q; j = int(p)
        return v[j] + (v[min(j+1, len(v)-1)]-v[j])*(p-j)
    return dict(repeats=repeats, seed=9162026,
                sale=[percentile(draws[0], q) for q in (.025, .975)],
                cancel=[percentile(draws[1], q) for q in (.025, .975)])


def replicated():
    summaries = []; clusters = []; equiv = different = 0; examples = []
    for seed in (2024, 2025, 2026, 41, 777):
        rng = random.Random(seed); counts = defaultdict(lambda: [0, 0]); raw = defaultdict(lambda: [0, 0])
        rejects = violations = attack_n = seed_diff = 0
        for source_index in range(1000):
            led, F, ds, dc = make_case5(rng, .1, .1)
            attacks = attacks4(F, led, rng)  # Same interleaving as v2 baseline.
            good = ref_accept(F, led, set('LDBZY'), (2, 3, 3))
            rejects += not good
            violation = ds > 3 or dc > 3 or sum(v['m'] == 0 and v['st'] == 'R' for v in led.values()) > 2
            violations += violation
            assert good != violation
            c = [0]*4
            for kind, G in attacks:
                attack_n += 1
                x = ref_accept(G, led, set('LDBZX'), (2, 3, 3))
                y = ref_accept(G, led, set('LDBZY'), (2, 3, 3))
                different += x != y
                seed_diff += x != y
                if x != y:
                    examples.append(dict(seed=seed, source_index=source_index, kind=kind,
                                         ledger=led, source=F, attack=G, X1=x, X2=y))
                for k, val in (('LDBZX', x), ('LDBZY', y)):
                    assert val == old(G, led, set(k), (2, 3, 3))
                    equiv += 1
                raw[kind][0] += not y; raw[kind][1] += 1
                if good:
                    counts[kind][0] += not y; counts[kind][1] += 1
                    if kind in ('거래 삭제', '취소 삭제'):
                        p = 0 if kind == '거래 삭제' else 2
                        c[p] += not y; c[p+1] += 1
            clusters.append(c)
        summaries.append(dict(seed=seed, files=1000, attacks=attack_n, unmodified_rejected=rejects,
                              assumption_violations=violations, X1_X2_differences=seed_diff,
                              macro_C=statistics.mean(100*a/b for a,b in counts.values()),
                              types=dict(counts), all_attacks=dict(raw)))
    return dict(seeds=summaries, v2_v3_attack_comparisons=equiv,
                X1_X2_differences=different, difference_examples=examples, cluster_CI=bootstrap(clusters))


def timings():
    out = []
    for n in (10, 100, 1000, 5000):
        led = {i: dict(m=0, amt=4, st='C', cum=2,
                       ev=[(1, False), (1, False), (2, True)]) for i in range(n)}
        F = (0, [(20, i, 1) for i in range(n)])
        for k in ('LDBZX', 'LDBZY'):
            A = (0, 0, n)
            assert ref_accept(F, led, set(k), A)
            samples = []
            for _ in range(9):
                t = time.perf_counter(); ref_accept(F, led, set(k), A)
                samples.append(1000*(time.perf_counter()-t))
            out.append(dict(transactions=n, records=n, events=3*n, K=k,
                            repetitions=9, median_ms=statistics.median(samples), min_ms=min(samples), max_ms=max(samples)))
    return dict(environment=dict(python=platform.python_version(), system=platform.system(),
                                 machine=platform.machine(), processor=platform.processor()), rows=out)


def consistency():
    from sensitivity import build
    from test_x2_error_cause import lag
    out = []; cases = build('orig')
    for mode in ('old', 'early'):
        for p in (.05, .1, .2):
            rng = random.Random(3); n = rejected = old_accepted = 0
            for led, F, _ in cases:
                bad = lag(led, p, rng, mode)
                contradiction = any(sum(a for a, f in v['ev'] if f) != v['cum'] for v in bad.values())
                accepted = ref_accept(F, bad, set('LDBZY'), (2, 3, 3))
                if contradiction:
                    n += 1; rejected += not accepted
                    old_accepted += old(F, bad, set('LDBZY'), (2, 3, 3))
                    assert not accepted
            out.append(dict(mode=mode, p=p, inconsistent=n, ref3_rejected=rejected, ref2_accepted=old_accepted))
    return out


def main():
    p = argparse.ArgumentParser(); p.add_argument('--output', required=True); args=p.parse_args()
    result = dict(controls=controlled(), A5=a5_control(), replication=replicated(), performance=timings(), consistency=consistency())
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print('Saved', args.output)


if __name__ == '__main__': main()
