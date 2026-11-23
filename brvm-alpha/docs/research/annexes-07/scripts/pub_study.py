# Étude (annexe 07) : ETUDE_DOSSIER désigne le dossier de travail de l'étude (pages/ et fichiers lus) ;
# les modules voisins (parse_views, names, evlib) sont lus dans le dossier de ce script.
import os, sys, glob, re, html
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd, evlib, names
S=os.path.join(os.environ.get('ETUDE_DOSSIER', '.'), '')
slug2name={l.strip().split('/')[-1]:None for l in open(S+'issuer_eq.txt')}
SLUGSYM={'air-liquide-ci':'SIVC','bank-africa-bf':'BOABF','bank-africa-bn':'BOAB','bank-africa-ci':'BOAC','bank-africa-ml':'BOAM','bank-africa-ng':'BOAN','bank-africa-sn':'BOAS','bbgci':'BBGC','bernabe-ci':'BNBC','bici-ci':'BICC','biic':'BICB','bollore-transport-logistics':'SDSC','cfao-motors-ci':'CFAC','cie-ci':'CIEC','coris-bank-international':'CBIBF','crown-siem-ci':'SEMC','ecobank-ci':'ECOC','ecobank-tg':'ETIT','filtisac-ci':'FTSC','lnb':'LNBB','movis-ci':'SVOC','nei-ceda-ci':'NEIC','nestle-ci':'NTLC','nsbc':'NSBC','onatel-bf':'ONTBF','oragroup':'ORGT','orange-ci':'ORAC','palm-ci':'PALC','safca-ci':'SAFC','saph-ci':'SPHC','servair-abidjan-ci':'ABJC','setao-ci':'STAC','sgb-ci':'SGBC','sib':'SIBC','sicable':'CABC','sicor':'SICC','sitab':'STBC','smb':'SMBC','sodeci':'SDCC','sogb':'SOGC','solibra':'SLBC','sonatel':'SNTS','sucrivoire':'SCRC','total':'TTLC','total-senegal-sa':'TTLS','totalenergies-marketing-sn':'TTLS','tractafric-ci':'PRSC','unilever-ci':'UNLC','uniwax-ci':'UNXC','vivo-energy-ci':'SHEC'}
rows=[]
for f in glob.glob(S+'pages/iss/*.html'):
    slug=f.split('/')[-1][:-5]; sym=SLUGSYM.get(slug)
    s=open(f,encoding='utf-8',errors='replace').read()
    for title,link in re.findall(r'<td class="views-field views-field-nothing"[^>]*>(.*?)</td>\s*<td class="views-field views-field-field-fichier[^"]*"[^>]*>.*?href="([^"]+)"',s,re.S):
        t=html.unescape(re.sub(r'<[^>]+>','',title)).strip()
        m=re.search(r'/files/(\d{8})',link); 
        try: fd=pd.Timestamp(m.group(1)) if m else pd.NaT
        except Exception: fd=pd.NaT
        rows.append((slug,sym,t,link,fd))
d=pd.DataFrame(rows,columns=['slug','symbol','title','link','file_date'])
def typ(t):
    t=t.lower()
    if re.search(r'1er trimestre|premier trimestre|1er\s*trim',t): return 'T1'
    if re.search(r'3[eè]?m?e? trimestre|troisi[eè]me trimestre|9 mois|neuf mois',t): return 'T3'
    if re.search(r'semestre|semestriel|30 juin',t): return 'S1'
    if re.search(r'etats? financiers|états? financiers|commissaires|annuel|exercice',t): return 'annuel'
    return 'autre'
d['type']=d.title.map(typ)
d.to_csv(S+'issuer_docs.csv',index=False)
print(len(d), d.symbol.isna().sum(), d.type.value_counts().to_dict(), d.file_date.min(), d.file_date.max())
d=d[d.symbol.notna()&d.file_date.notna()&d.type.isin(['T1','S1','T3','annuel'])]
# une publication par (symbole, type, date) ; regrouper les documents du même jour
ev=d.sort_values('file_date').drop_duplicates(['symbol','file_date']).copy()
ev['event_date']=ev['file_date']
# month distribution
print(pd.crosstab(ev.type,ev.file_date.dt.month).to_string())
a=evlib.load()
# baseline mean |AR| per symbol
base=a.groupby('symbol')['ar'].apply(lambda x:x.abs().mean())
w={'pre5':(-5,-1),'d0':(0,0),'d01':(0,1),'d12':(1,2),'post':(3,22)}
r=evlib.event_windows(a,ev,windows=w)
# event aligned at first session >= file_date ; news likely after close -> reaction at d0 or d1
r['absr']=r['d01'].abs(); r['base2']=2*r.symbol.map(base)
r['abs_ratio']=r['absr']/r['base2']
print('n',len(r)); print(r.groupby('type')[['abs_ratio','abn_value']].median().round(2).to_string())
print('all: median |AR[0,1]|/normal = %.2f ; median abn value = %.2f'%(r.abs_ratio.median(), r.abn_value.median()))
# drift conditional on initial reaction sign (d01) -> post [+3,+22]
r['sgn']=np.sign(r['d01'])
r['cont']=r['sgn']*r['post']
print(evlib.summarize(r[r.sgn!=0],['cont']).round(3).to_string())
for t,sub in r[r.sgn!=0].groupby('type'): print(t, evlib.summarize(sub,['cont']).round(3).to_string(header=False))
# quintile of reaction
r['q']=pd.qcut(r['d01'],5,labels=False,duplicates='drop')
print(r.groupby('q')[['d01','post']].agg(['count','mean']).round(4).to_string())
r.to_csv(S+'pub_events.csv',index=False)
