"""Executable regression tests for schema/visible-observation boundary."""
from copy import deepcopy
from ref3 import ref_accept, ref_accept_id


def main():
    n = 0
    def check(actual, expected):
        nonlocal n
        n += 1
        assert actual is expected, (n, actual, expected)
    led = {1: dict(m=0, amt=4, st='C', cum=2,
                   ev=[(1, False), (1, False), (2, True)])}
    A = (0, 0, 2)
    check(ref_accept((0, []), led, set('LDBZY'), A), True)
    for F in [(0, [(30, 1, 1)]), (0, [(20, 1, 0)]),
              (0, [(20, 1, -1)]), (0, [(20, 1, True)]),
              (0, [(20, 1, 1.0)]), (0, [(20, 1)]),
              (0, [(10, 1, 4, 0)]), ('0', []), None]:
        check(ref_accept(F, led, set(), A), False)
    bad = deepcopy(led); bad[1]['ev'][2] = (2, False)
    check(ref_accept((0, []), bad, set('LDBZY'), A), False)
    # The contradiction is invisible without one of its two components.
    check(ref_accept((0, []), bad, set('LDBZX'), A), True)
    check(ref_accept((0, []), bad, set('LDBY'), (0, 0, 4)), True)
    bad = deepcopy(led); bad[1].update(st='U')
    check(ref_accept((0, []), bad, set('LDBZY'), (1, 1, 4)), False)
    hidden = deepcopy(led); hidden[1].update(st=object(), cum=object(), ev=object())
    check(ref_accept((0, []), hidden, set('L'), A), True)
    hidden = deepcopy(led); hidden[1]['cum'] = object()
    check(ref_accept((0, []), hidden, set('LDBY'), A), True)
    for F in [(0, [(20, 1, 1, -1)]), (0, [(20, 1, 1, 0), (20, 1, 1, 0)]),
              (0, [(20, 1, 1, 2)]), (0, [(20, 1, 1)])]:
        check(ref_accept_id(F, led, set('LDBZY'), A), False)
    check(ref_accept_id((0, [(20, 1, 1, 0)]), led, set('LDBZY'), A), True)
    bad = deepcopy(led); bad[2] = dict(m=1, amt=3, st='U', cum=1, ev=[(1, True)])
    check(ref_accept((0, []), bad, set('LDBZY'), A), False)
    bad = deepcopy(led); bad[1].update(cum=3, ev=[(2, False)])
    check(ref_accept((0, []), bad, set('LDBZX'), A), False)
    check(ref_accept_id((0, []), led, set('L'), A), False)
    print('ref3 boundary checks:', n, 'passed')


if __name__ == '__main__':
    main()
