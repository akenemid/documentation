"""Parse Drupal 7 'views-table' listings from brvm.org pages."""
import re, html, sys, json
def parse(path):
    s=open(path,encoding='utf-8',errors='replace').read()
    m=re.search(r'<table class="views-table[^"]*"[^>]*>(.*?)</table>',s,re.S)
    if not m: return None, []
    t=m.group(1)
    heads=[re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]+>','',h))).strip() for h in re.findall(r'<th[^>]*>(.*?)</th>',t,re.S)]
    hcls=re.findall(r'<th class="views-field ([^"]*)"',t)
    rows=[]
    for tr in re.findall(r'<tr[^>]*>(.*?)</tr>',t,re.S)[1:]:
        cells=[]
        for cls,td in re.findall(r'<td class="views-field ([^"]*)"[^>]*>(.*?)</td>',tr,re.S):
            iso=re.search(r'content="([^"]+)"',td)
            links=re.findall(r'href="([^"]+)"',td)
            text=re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]+>','',td))).strip()
            cells.append({'cls':cls.split()[0],'text':text,'iso':iso.group(1) if iso else None,'links':links})
        rows.append(cells)
    last=re.search(r'pager-last"><a[^>]*href="[^"]*page=(\d+)"',s)
    return {'heads':heads,'cls':hcls,'last_page':int(last.group(1)) if last else 0}, rows
if __name__=='__main__':
    for p in sys.argv[1:]:
        meta,rows=parse(p)
        print('=== ',p, meta, 'rows=',len(rows))
        for r in rows[:4]:
            print('   ', [(c['cls'],c['text'][:70],c['iso'],[l[-90:] for l in c['links']]) for c in r])
