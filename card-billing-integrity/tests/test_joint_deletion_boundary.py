"""Joint deletion with fixed sale states, using each level's own accepted originals.

Expected acceptance uses only the observed U/R count minus sent sale count.
No verifier cost helper or reflection subset is used by the expected-value code.
Amount and ID files are generated from the existing paired seed-2024 builders.
"""
from collections import Counter
from ref3 import ref_accept, ref_accept_id
from sensitivity import build
from sensitivity_s4 import build_id

LEVELS = ('LDB', 'LDBZ', 'LDBX', 'LDBZX', 'LDBY', 'LDBZY')


def main():
    amount = build('orig')
    ids = build_id()[0]
    checks, bad = Counter(), Counter()
    for (led, F, _), (led_i, F_i, _, _) in zip(amount, ids):
        assert led == led_i
        assert F == (F_i[0], [tuple(r[:3]) for r in F_i[1]])
        total_pending_sales = sum(v['m'] == F[0] and v['st'] in 'UR' for v in led.values())
        sent_sales = [r for r in F[1] if r[0] == 10]
        original_deferral = total_pending_sales - len(sent_sales)
        for cs in range(5):
            A = (2, cs, 3)
            for level in LEVELS:
                modes = [('amount', F, ref_accept)]
                if set(level) & set('XY'):
                    modes.append(('ID', F_i, ref_accept_id))
                for mode, original, judge in modes:
                    if not judge(original, led, set(level), A):
                        continue
                    for sale in sent_sales:
                        modified = (original[0], [r for r in original[1] if r[1] != sale[1]])
                        expected = original_deferral + 1 <= cs
                        key = f'{level}-{mode}'
                        checks[key] += 1
                        bad[key] += judge(modified, led, set(level), A) != expected
    print('Joint deletion: own accepted originals, seed 2024, CR=2, cc=3, cs=0..4')
    for key in sorted(checks):
        print(f'{key}: checks={checks[key]}, mismatch={bad[key]}')
    assert len(amount) == len(ids) == 1000
    assert checks and not any(bad.values())
    print('OK')


if __name__ == '__main__':
    main()
