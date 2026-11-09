"""v3 / v2 ID decisions on the existing S4 domain, including attacks."""
from sensitivity_s4 import build_id
from ref2id import ref_accept_id as old
from ref3 import ref_accept_id


def main():
    n = 0
    cases, _ = build_id()
    for led, F, a13, aid in cases:
        for K in (set('LDBZX'), set('LDBZY')):
            for A in ((2, 3, 3), (2, 3, 1)):
                for G in [F] + [x[1] for x in a13 + aid]:
                    assert ref_accept_id(G, led, K, A) == old(G, led, K, A)
                    n += 1
    print('ref2id/ref3 ID comparisons', n, 'mismatches 0')


if __name__ == '__main__': main()
