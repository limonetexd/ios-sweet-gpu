#!/bin/bash
# sum.sh TAG : one-screen summary of logs/xnu-TAG.txt
cd /Users/pablo/Developer/ios-sweet; L=logs/xnu-$1.txt
echo "== $1  gfsr $(rg -c 'SMMU gfsr' $L) notfinish $(rg -c 'THE GPU DID NOT FINISH' $L) arena $(rg -c 'table arena full' $L)  crashes: $(rg -o 'CRASH [A-Za-z.]+\[' $L | sort | uniq -c | sort -rn | head -4 | tr '\n' ' ')"
rg -o 'CPUFREQ[^|]{0,80}|page lists kept[^|]{0,40}|cleared [0-9]+ ms after' $L | sort -u | head -4
python3 tools/sweet-passlog-summary.py $L 2>&1 | rg -A4 '== backboardd' | rg 'busy' | cut -c1-110
rg -o 'PBGRABsovXm_TimgA2Xhfc_Isrc +draws [0-9]+, in [0-9]+ cbs, cb time sum [0-9.]+ ms' $L | awk '{c+=$5; w+=$10} END{printf "cbs %d wall/cb %.2f ms  ",c,w/c}'
C=$(rg -o 'PBGRABsovXm_TimgA2Xhfc_Isrc +draws [0-9]+, in [0-9]+ cbs' $L | awk '{c+=$5} END{print c}')
rg -o 'cpu [0-9.]+ ms of wall' $L | awk -v c=$C '{s+=$2} END{printf "cpu/cb %.2f ms\n",s/c}'
rg -o 'RedwoodGPU: [0-9]+ waits of [0-9]+ us' $L | awk '{n+=$2; t+=$2*$5} END{printf "waits %d mean %.0f us  ",n,t/n}'
rg -o '[0-9]+ submissions in [0-9]+ ms.{0,120}us a submission; [0-9]+ first cleans of [0-9]+ MB' $L | awk '{s+=$1; for(i=1;i<=NF;i++){if($i=="us"&&$(i+1)=="a")f+=$1*$(i-1); if($i=="first"){fc+=$(i-1); fm+=$(i+3)}}} END{printf "subs %d flush %.0f us/sub first cleans %d of %d MB  ",s,f/s,fc,fm}'
rg -o 'IOSurfaces taken as buffers in [0-9]+ us' $L | awk '{n++; s+=$(NF-1)} END{printf "take %.0f us  ",s/n}'
rg -o 'presents \([0-9]+ us average' $L | awk '{gsub("\\(","",$2); if($2>0){n++; t+=$2}} END{printf "present %.0f us\n",t/n}'
rg -o 'SWEET FPS: [0-9]+ swaps in [0-9]+ ms \([0-9]+ ms longest, [0-9]+ late' $L | awk '{n++; s+=$3; if($3>m)m=$3; if($3>=10){a++; as+=$3}; h[int($3/10)]++; if($3>=50){f++; fl+=$11}} END{printf "swaps %d max/s %d active s %d (%.1f/s)  hist:",s,m,a,as/a; for(k=0;k<7;k++) printf " %d0s:%d",k,h[k]; printf "  late in >=50 s: %.1f avg\n", f?fl/f:0}'
rg -o 'kept memory \([a-z ]+\): [0-9]+ reused, [0-9]+ made' $L | tail -1
rg -o 'SWEET THERM: cpu [0-9.]+ a55 [0-9.]+ big [0-9.]+ gpu [0-9.]+' $L | awk '{if($4>c)c=$4; if($8>b)b=$8; if($10>g)g=$10} END{print "max C cpu",c,"big",b,"gpu",g}'
