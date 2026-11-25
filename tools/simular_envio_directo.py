"""Línea base de envío directo (un camión por pedido) con las coordenadas corregidas.

Replica en Python la vista vw_ComparativaTiposVehiculo para contrastar sus cifras.
Uso: python tools/simular_envio_directo.py database/original/script_sqlserver.sql \n         database/03_corregir_coordenadas.sql
"""
import re,math,collections,sys
t=open(sys.argv[1],encoding='utf-16').read()
c=open(sys.argv[2],encoding='utf-8').read()
dest={int(i):(float(a),float(b)) for i,a,b in re.findall(r"^\((\d+), \d+, '[^']*', '[^']*', ([-\d.]+), ([-\d.]+)\)",c,re.M)}
prod={int(a):(int(f),int(cd)) for a,f,cd in re.findall(r"\[Productos\].*VALUES \((\d+), N'[^']*', CAST\([^)]*\)\), (\d+), (\d+)\)",t)}
ped={int(p):int(d) for p,d in re.findall(r"\[Pedidos\].*VALUES \((\d+), CAST\(N'[^']*' AS DateTime\), \d+, (\d+)\)",t)}
L=collections.defaultdict(list)
for p,pr,q in re.findall(r"\[LineasPedido\].*VALUES \((\d+), \d+, (\d+), (\d+)\)",t): L[int(p)].append((prod[int(pr)],int(q)))
def hav(a,b,c,d):
    r=math.radians;x=math.sin(r(c-a)/2)**2+math.cos(r(a))*math.cos(r(c))*math.sin(r(d-b)/2)**2;return 6371.0088*2*math.atan2(math.sqrt(x),math.sqrt(1-x))
tipos=[('12t',12000,24,2.0,.09,.03,95000,20000,8,4500,900,100000),('18t',18000,28,2.5,.10,.035,120000,25000,8,5000,1100,110000),('40t',33000,33,3.0,.12,.045,190000,40000,8,7000,1800,130000)]
D={p:hav(41.5381,2.4445,*dest[d])*1.25 for p,d in ped.items()}
print('dist ida km: min %.0f media %.0f max %.0f'%(min(D.values()),sum(D.values())/len(D),max(D.values())), 'destinos usados',len(set(ped.values())))
for n,cap,cons,frio,mant,neu,pa,vr,vu,seg,imp,kma in tipos:
    v=70;lkm=cons/100+frio/v;pr=1.42-.049;ckm=lkm*pr+.04+mant+neu+((pa-vr)/vu+seg+imp)/kma
    tot=ext=co2=km=0;ok=0;U=0
    for p,d in ped.items():
        Dk=D[p];h=Dk/v;paus=math.floor(h/4.5)*.75;desc=max(math.ceil(2*h/9)-1,0);descI=max(math.ceil(h/9)-1,0)
        ht=2*(h+paus)+1+.5;cost=2*Dk*ckm+ht*22+(desc+1)*55+desc*45
        tot+=cost;ext+=120+Dk*1.85;co2+=2*Dk*lkm*2.68;km+=2*Dk
        u=sum(q for _,q in L[p]);U+=u
        listo=1+max(f for (f,cc),_ in L[p]);cad=listo+min(cc for (f,cc),_ in L[p])
        arr=listo*24+6+1+h+paus+descI*11
        ok+=(u<=cap) and arr<=cad*24-24
    print(n,'€/km %.3f'%ckm,'viables',ok,'cota',math.ceil(U/cap),'km %.0f'%km,'propio %.0f'%tot,'ext %.0f'%ext,'tCO2 %.1f'%(co2/1000))
