import struct,sys
BS=4096
f=open(sys.argv[1],'rb'); o=open(sys.argv[2],'wb')
import os
size=os.fstat(f.fileno()).st_size; total=size//BS; assert size%BS==0
o.write(b'\0'*28)
zero=bytes(BS); chunks=0; run=None; n=0; buf=[]
def flush():
    global run,n,buf,chunks
    if not n: return
    if run=='raw':
        o.write(struct.pack('<HHII',0xCAC1,0,n,12+n*BS)); o.writelines(buf)
    else:
        # FILL, not DONT_CARE: zero blocks inside files must really be written
        o.write(struct.pack('<HHII',0xCAC2,0,n,16)); o.write(bytes(4))
    chunks+=1; n=0; buf=[]
for i in range(total):
    b=f.read(BS); k='hole' if b==zero else 'raw'
    if k!=run or n>=25600: flush(); run=k
    if k=='raw': buf.append(b)
    n+=1
flush()
o.seek(0); o.write(struct.pack('<IHHHHIIII',0xed26ff3a,1,0,28,12,BS,total,chunks,0)); o.close()
print('blocks',total,'chunks',chunks)
