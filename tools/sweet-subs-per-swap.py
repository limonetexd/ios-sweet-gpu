#!/usr/bin/env python3
"""Per-boot sums from SWEET FPS and RedwoodGPU lines: swaps/s, late swaps, submissions per swap,
kernel cache-clean CPU time. Host only. Usage: python3 -I tools/sweet-subs-per-swap.py logs/xnu-TAG.txt ..."""
import re,sys
for f in sys.argv[1:]:
    t=open(f,errors='replace').read()
    fps=re.findall(r'SWEET FPS: (\d+) swaps in (\d+) ms \((\d+) ms longest, (\d+) late\), (\d+) presents \((\d+) us average, (\d+) us longest, (\d+) waited',t)
    act=[x for x in fps if int(x[0])>0]
    sw=[int(x[0]) for x in act]
    print(f, 'FPS lines',len(fps),'active secs',len(act),'swaps',sum(sw),'late',sum(int(x[3]) for x in act),
      'max swaps/s',max(sw or [0]),'secs>=10',sum(s>=10 for s in sw),'waited',sum(int(x[7]) for x in act))
    print('  swaps/s hist', sorted(sw))
    g=re.findall(r'RedwoodGPU: (\d+) submissions in (\d+) ms: (\d+) command buffers and (\d+) buffers named, (\d+) KB out of the cache in (\d+) us a submission; (\d+) first cleans of (\d+) MB',t)
    S=sum(int(x[0]) for x in g); ms=sum(int(x[1]) for x in g); cb=sum(int(x[2]) for x in g); bn=sum(int(x[3]) for x in g)
    cache_us=sum(int(x[0])*int(x[5]) for x in g); kb=sum(int(x[0])*int(x[4]) for x in g)
    print('  GPU lines',len(g),'subs',S,'in s',ms/1000,'cmdbufs',cb,'bufs named/sub',round(bn/max(S,1),1),
      'cache CPU s',round(cache_us/1e6,1),'cache GB',round(kb/1e6,1),'subs/swap',round(S/max(sum(sw),1),1))
