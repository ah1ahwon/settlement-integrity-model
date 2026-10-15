import random, collections
import m2b, m4
from m4 import *
m4.explainable=m2b.explainable; m2b.CR=2
from run9 import make_case5
from props import KS, leq
rng=random.Random(8); C=[]
for _ in range(300):
    led,F,_,_=make_case5(rng,0.1,0.1); C.append((led,F,attacks4(F,led,rng)))
def why(G,led,K,c):
    a=m2b.atoms(G,led,{k for k in K if k not in 'XY'},c); ex=[] if extra_ok(G,led,K,c) else ['X/Y취소규칙']
    return [n for n,v in a.items() if not v]+ex
for c in (1,2):
    cnt=collections.Counter(); ex=[]
    for led,F,A in C:
        for kd,G in [('정당',F)]+list(A):
            for a in KS:
                for b in KS:
                    if a!=b and leq(a,b) and (not explainable4(G,led,a,c)) and explainable4(G,led,b,c):
                        cnt[(kd,''.join(sorted(a)),''.join(sorted(b)),tuple(why(G,led,a,c)),tuple(why(G,led,b,c)))]+=1
    print(f'c={c}: 남은 위반 유형')
    for k,v in cnt.most_common(8): print('  ',v,'건',k)
