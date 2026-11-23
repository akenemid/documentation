# Étude (annexe 07) : ETUDE_DOSSIER désigne le dossier de travail de l'étude (pages/ et fichiers lus) ;
# les modules voisins (parse_views, names, evlib) sont lus dans le dossier de ce script.
import os, sys, glob, re, pandas as pd, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parse_views, names
B=os.path.join(os.environ.get('ETUDE_DOSSIER', '.'), 'pages', '')
files=[B+'dividendes.html']+sorted(glob.glob(B+'p/dividendes_*.html'),key=lambda f:int(re.search(r'_(\d+)\.html',f).group(1)))
rows=[]
for f in files:
    m,rs=parse_views.parse(f)
    for r in rs:
        c={x['cls']:x for x in r}
        link=(c.get('views-field-field-avis-dividende-esv',{}).get('links') or [None])[0]
        fd=None
        if link:
            mm=re.search(r'/files/(\d{8})',link)
            if mm:
                try: fd=pd.Timestamp(mm.group(1))
                except Exception: fd=None
        amt=c.get('views-field-field-montant-du-dividende-net',{}).get('text','')
        am=re.sub(r'[^\d,\.]','',amt.replace(' ','')).replace(',','.')
        rows.append(dict(emetteur=c['views-field-field-emetteur-esv']['text'],
            exercice=c.get('views-field-field-exercice-comptable-esv',{}).get('text'),
            pay=c.get('views-field-field-date-de-paiement-esv',{}).get('iso'),
            ex=c.get('views-field-field-date-ex-dividende',{}).get('iso'),
            amount=float(am) if am and am!='.' else np.nan, amount_txt=amt, avis=link, avis_date=fd, page=f.split('/')[-1]))
df=pd.DataFrame(rows)
for k in ['pay','ex']: df[k]=pd.to_datetime(df[k].str[:10],errors='coerce')
df['symbol']=df['emetteur'].map(names.to_symbol)
df.to_csv(B+'../brvm_dividends.csv',index=False)
print(len(df), 'unmapped:', df[df.symbol.isna()].emetteur.unique())
print(df.head(3).to_string()); print(df.ex.min(), df.ex.max())
