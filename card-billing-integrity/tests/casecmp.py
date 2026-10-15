import random, collections
from ref import ref_accept
from run9 import make_case5
from m4 import attacks4
rng=random.Random(2024); n=0; dis=collections.Counter(); tot=collections.Counter(); amb_led=0; ledn=0
Aa=(2,3,3)
for _ in range(1000):
    led,F,ds,dc=make_case5(rng,0.1,0.1); A=attacks4(F,led,rng)
    for kd,G in [('정당 파일',F)]+list(A):
        x1=ref_accept(G,led,set('LDBZX'),Aa); x2=ref_accept(G,led,set('LDBZY'),Aa)
        n+=1; tot[kd]+=1
        if x1!=x2: dis[(kd,'X1+Z수락/X2거절' if x1 else 'X1+Z거절/X2수락')]+=1
print('총 비교',n,'건 (정당 1000 + 변조',n-1000,')  판정 불일치',sum(dis.values()),'건')
for k,v in sorted(dis.items()): print(' ',k,v,'/',tot[k[0]])
