import struct,sys
f=open(sys.argv[1],'rb'); o=open(sys.argv[2],'wb')
m,maj,mi,fh,ch,bs,tb,tc,_=struct.unpack('<IHHHHIIII',f.read(28)); assert m==0xed26ff3a
f.seek(fh)
for i in range(tc):
    t,_,sz,total=struct.unpack('<HHII',f.read(ch)); data=total-ch
    if t==0xCAC1:
        o.write(f.read(data))
    elif t==0xCAC2:
        v=f.read(4)
        if v==b'\0\0\0\0': o.seek(sz*bs,1)
        else: o.write(v*(sz*bs//4))
    elif t==0xCAC3: o.seek(sz*bs,1)
    elif t==0xCAC4: f.seek(data,1)
    else: raise SystemExit('bad chunk %x'%t)
o.truncate(tb*bs); o.close(); print('blocks',tb,'size',tb*bs)
