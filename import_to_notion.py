import json, os, sys, urllib.request, urllib.error
TOKEN=os.environ.get('NOTION_TOKEN')
if not TOKEN: raise SystemExit('Missing GitHub secret NOTION_TOKEN')
DB={
 'stars':'32ebaf348bba80ed8348cd81e5ef88fb','planets':'32ebaf348bba8076982afb7b42262ba4','moons':'32fbaf348bba80a399c0f1fae5d193bc'
}
HEAD={'Authorization':f'Bearer {TOKEN}','Notion-Version':'2022-06-28','Content-Type':'application/json'}
def req(method,path,data=None):
    body=json.dumps(data).encode() if data is not None else None
    r=urllib.request.Request('https://api.notion.com/v1'+path,data=body,headers=HEAD,method=method)
    try:
        with urllib.request.urlopen(r) as resp: return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise SystemExit(f'Notion API error {e.code}: {e.read().decode()}')
def schema(dbid): return req('GET',f'/databases/{dbid}')['properties']
SCHEMAS={k:schema(v) for k,v in DB.items()}
def spectral(t):
    return 'O' if t>=30000 else 'B' if t>=10000 else 'A' if t>=7500 else 'F' if t>=6000 else 'G' if t>=5200 else 'K' if t>=3700 else 'M'
def life(v): return 'Complex Life' if v>=2 else 'Microbial Life' if v==1 else 'No Known Life'
def geo(v): return 'Extreme Geologic Activity' if v>=3 else 'Active' if v==2 else 'Low Activity' if v==1 else 'Geologically Dead'
def atmosphere(o): return 'None' if not o.get('atmobasegas') or o.get('atmobasegas')=='none' else str(o.get('atmobasegas')).title()
def pclass(p):
    return 'Gas Giant' if p.get('gas',0)>.5 else 'Ice World' if p.get('ice',0)>.45 else 'Super-Earth' if p.get('mass',0)>=2 else 'Dwarf Planet' if p.get('mass',0)<.05 else 'Terrestrial Planet'
def mclass(m): return 'Icy Moon' if m.get('ice',0)>.45 else 'Rocky Moon' if m.get('rock',0)>.6 else 'Mixed Moon'
def prop_value(kind, val):
    if val is None or val=='': return None
    if kind=='title': return {'title':[{'text':{'content':str(val)}}]}
    if kind=='rich_text': return {'rich_text':[{'text':{'content':str(val)[:1900]}}]}
    if kind=='number':
        try: return {'number':float(val)}
        except Exception: return None
    if kind=='checkbox': return {'checkbox':bool(val)}
    if kind=='select': return {'select':{'name':str(val)}}
    if kind=='multi_select': return {'multi_select':[{'name':str(x).strip()} for x in (val if isinstance(val,list) else str(val).split(';')) if str(x).strip()]}
    if kind=='url': return {'url':str(val)}
    return None
def build_props(dbkey, values, relations=None):
    props={}; sch=SCHEMAS[dbkey]
    for name,val in values.items():
        if name not in sch: continue
        t=sch[name]['type']
        if t in ('formula','rollup','created_time','last_edited_time','created_by','last_edited_by','button','unique_id'): continue
        if t=='relation': continue
        pv=prop_value(t,val)
        if pv is not None: props[name]=pv
    if relations:
        for name,page_id in relations.items():
            if name in sch and sch[name]['type']=='relation': props[name]={'relation':[{'id':page_id}]}
    return props
def find_page(dbid, name):
    data={'filter':{'property':'Name','title':{'equals':name}},'page_size':1}
    res=req('POST',f'/databases/{dbid}/query',data)['results']
    return res[0]['id'] if res else None
def create_or_get(dbkey, values, relations=None):
    name=values['Name']; existing=find_page(DB[dbkey],name)
    if existing:
        print('SKIP existing',dbkey,name); return existing
    data={'parent':{'database_id':DB[dbkey]},'properties':build_props(dbkey,values,relations)}
    page=req('POST','/pages',data); print('CREATED',dbkey,name); return page['id']
def star_values(s): return {'Name':s.get('name','Unnamed Star'),'Description':f"{s.get('name','Unnamed Star')} is a generated {spectral(s.get('temp',0))}-class star with {s.get('luma',0):.3f} solar luminosity.",'Luminosity (Solar)':s.get('luma'),'Solar Temperature':s.get('temp'),'System Age (bn years)':s.get('age',0)/1000,'Spectral Class':spectral(s.get('temp',0)),'Star Type':'White Dwarf' if s.get('WD') else 'Main Sequence Star','System Type':'Primary Star System' if s.get('isPrimary') else 'Star System','Survey Status':'Generated'}
def planet_values(p,s): return {'Name':p.get('name'),'Description':f"{p.get('name')} orbits {s.get('name')} at {p.get('distanceFromParent'):.3f} AU. Classification: {pclass(p)}. Life: {life(p.get('life',0))}.",'Planetary Description':f"Generated world imported from .solar source. Rock {p.get('rock',0):.2f}, ice {p.get('ice',0):.2f}, gas {p.get('gas',0):.2f}.",'Classification':pclass(p),'Planet Distance from Star (AU)':p.get('distanceFromParent'),'Distance from Star':f"{p.get('distanceFromParent'):.3f} AU",'Mass':p.get('mass'),'Raw Mass':p.get('mass'),'Day Length':f"{p.get('dayCycle',0):.2f} days",'Atmospheric Composition':atmosphere(p),'Atmospheric Pressure':p.get('atmothickness'),'Atmosphere Density Factor':p.get('atmothickness'),'Life Sign':life(p.get('life',0)),'Fluid State':'Surface Liquid Present' if p.get('liquid')=='0' else 'No Stable Surface Liquid','Tectonic Status':geo(p.get('geoactive',0)),'Star Luminosity (Solar)':s.get('luma'),'System Age (bn years)':s.get('age',0)/1000,'Strategic Resources':'To be assessed'}
def moon_values(m,p): return {'Name':m.get('name'),'Lunar Description':f"{m.get('name')} is a {mclass(m).lower()} orbiting {p.get('name')}.",'Calculated Orbital Distance':m.get('distanceFromParent'),'Orbit Period':f"{m.get('dayCycle',0):.2f} days",'Rotational Period':f"{m.get('dayCycle',0):.2f} days",'Atmosphere':atmosphere(m),'Life Sign':life(m.get('life',0)),'Satellite Class':mclass(m),'Tidal Locking Prediction':'Tidally Locked' if m.get('tidalLock') else 'Independent Rotation','Strategic Value':'Astrobiological Interest' if m.get('life') else 'Low'}
def main(path):
    system=json.load(open(path,encoding='utf-8'))
    star_id=create_or_get('stars',star_values(system))
    for p in system.get('planets',[]):
        pid=create_or_get('planets',planet_values(p,system),{'Parent Star':star_id})
        for m in p.get('moons',[]):
            create_or_get('moons',moon_values(m,p),{'Parent Planet':pid})
    print('DONE')
if __name__=='__main__':
    if len(sys.argv)<2: raise SystemExit('Usage: python scripts/import_to_notion.py imports/system.solar')
    main(sys.argv[1])
