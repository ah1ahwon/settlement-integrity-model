"""Strict input boundary for the published model; ref2 is retained for v2 logs.

X/Y are the code names for X1/X2. Only visible observation fields are
validated. Invalid configuration, malformed files and inconsistent visible
observations return False. Hidden fields cannot affect the result.
"""
from ref2 import ref_accept as _amount
from ref2id import ref_accept_id as _ids


def _int(x, minimum=0):
    return type(x) is int and x >= minimum


def prepare(F, led, K, A, use_ids=False):
    K = set(K)
    if K - set('LDBZXY') or ('L' not in K and K):
        raise ValueError('unsupported information level')
    if 'B' in K and 'D' not in K:
        raise ValueError('B requires D')
    if use_ids and not K.intersection('XY'):
        raise ValueError('ID observations require an approved event list')
    if len(A) != 3 or not all(_int(x) for x in A):
        raise ValueError('nonnegative integer budgets required')
    if len(F) != 2 or not _int(F[0]) or not isinstance(F[1], (list, tuple)):
        raise ValueError('invalid file container')
    for r in F[1]:
        if not isinstance(r, (list, tuple)) or len(r) < 3:
            raise ValueError('invalid record')
        t, i, a = r[:3]
        if type(t) is not int or t not in (10, 20) or not _int(i) or not _int(a, 1):
            raise ValueError('invalid record value')
        if len(r) != (4 if use_ids and t == 20 else 3):
            raise ValueError('invalid record length')
        if use_ids and t == 20 and not _int(r[3]):
            raise ValueError('invalid event identifier')
    if 'L' not in K:
        return {}, K
    if not isinstance(led, dict):
        raise ValueError('invalid ledger')
    clean = {}
    for i, v in led.items():
        if not _int(i) or not _int(v['m']) or not _int(v['amt'], 1):
            raise ValueError('invalid authorization')
        st = v['st'] if 'D' in K else 'C'
        if 'D' in K and st not in ('U', 'C', 'R'):
            raise ValueError('invalid observed state')
        # D observes only prior billing, not the C/R distinction.
        if 'D' in K and 'B' not in K and st != 'U':
            st = 'C'
        ev = []
        if K & set('XY'):
            if not isinstance(v['ev'], (list, tuple)):
                raise ValueError('invalid event list')
            for e in v['ev']:
                if len(e) != 2 or not _int(e[0], 1):
                    raise ValueError('invalid cancellation amount')
                if 'Y' in K and type(e[1]) is not bool:
                    raise ValueError('invalid reflection flag')
                ev.append((e[0], e[1] if 'Y' in K else False))
            if sum(a for a, _ in ev) > v['amt']:
                raise ValueError('cancellations exceed authorization')
        cum = v['cum'] if 'Z' in K else 0
        if not _int(cum) or cum > v['amt']:
            raise ValueError('invalid reflected total')
        if 'Y' in K:
            derived = sum(a for a, f in ev if f)
            if 'Z' in K and cum != derived:
                raise ValueError('Z and X2 disagree')
            cum = derived
        elif 'X' in K and 'Z' in K:
            totals = {0}
            for a, _ in ev:
                totals |= {v+a for v in totals if v+a <= cum}
            if cum not in totals:
                raise ValueError('Z has no compatible reflection subset')
        if 'D' in K and (st == 'U' or ('B' in K and st == 'R')) and cum:
            raise ValueError('A4 excludes reflected cancellations in this observed state')
        clean[i] = dict(m=v['m'], amt=v['amt'], st=st, cum=cum, ev=ev)
    # X2 determines Z; the normalization introduces no extra information.
    if 'Y' in K:
        K.add('Z')
    return clean, K


def _judge(F, led, K, A, use_ids):
    try:
        clean, visible = prepare(F, led, K, A, use_ids)
        return (_ids if use_ids else _amount)(F, clean, visible, A)
    except (ValueError, TypeError, KeyError, IndexError, AttributeError):
        return False


def ref_accept(F, led, K, A):
    return _judge(F, led, K, A, False)


def ref_accept_id(F, led, K, A):
    return _judge(F, led, K, A, True)
