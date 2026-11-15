"""Refresh the README from public GitHub + npm data. Python standard library only.

Uses the public GitHub contribution calendar (same counts as the profile),
public account/repository REST endpoints, and npm's last-month download API.
An optional GH_TOKEN raises REST rate limits. No private repository data is read.
Use --offline to render the committed snapshot without network requests.
"""
from pathlib import Path
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from html import escape
import concurrent.futures, json, math, os, re, sys, urllib.request

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'assets'/'v2'
USER='rythmern02'
BG='#071321'; FG='#edf8ff'; MUTED='#9db5cd'; CYAN='#70dcf1'

def fetch(url):
 headers={'User-Agent':'Mozilla/5.0 (compatible; rythmern02-profile/2.0)','Accept':'text/html' if url.startswith('https://github.com/users/') else 'application/json'}
 token=os.environ.get('GH_TOKEN')
 if token and url.startswith('https://api.github.com/'):
  headers['Authorization']='Bearer '+token
 with urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=40) as r:
  body=r.read().decode()
 return json.loads(body) if body.lstrip().startswith(('{','[')) else body

class Calendar(HTMLParser):
 def __init__(self):
  super().__init__();self.cells={};self.counts={};self.tip=None;self.body=''
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag=='td' and 'data-date' in a:
   self.cells[a['id']]={'date':a['data-date'],'level':int(a['data-level'])}
  if tag=='tool-tip':
   self.tip=a.get('for');self.body=''
 def handle_data(self,s):
  if self.tip:self.body+=s
 def handle_endtag(self,tag):
  if tag=='tool-tip' and self.tip:
   m=re.search(r'([\d,]+) contributions?',self.body)
   if not m and not self.body.strip().startswith('No contributions'):
    raise ValueError('Unrecognized GitHub contribution tooltip: '+self.body)
   self.counts[self.tip]=int(m.group(1).replace(',','')) if m else 0
   self.tip=None

def collect(today):
 urls={
 'user':f'https://api.github.com/users/{USER}',
 'calendar':f'https://github.com/users/{USER}/contributions?from={today.year}-01-01&to={today.isoformat()}',
 'downloads':'https://api.npmjs.org/downloads/point/last-month/gpu402',
 'package':'https://registry.npmjs.org/gpu402/latest'}
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
  jobs={k:ex.submit(fetch,url) for k,url in urls.items()}
  data={k:j.result() for k,j in jobs.items()}
 repos=[];page=1
 while True:
  batch=fetch(f'https://api.github.com/users/{USER}/repos?per_page=100&page={page}')
  if not isinstance(batch,list):raise ValueError('Invalid repository response')
  repos+=batch
  if len(batch)<100:break
  page+=1
 c=Calendar();c.feed(data['calendar'])
 days=[]
 for key,cell in c.cells.items():
  d=date.fromisoformat(cell['date'])
  if d.year!=today.year or d>today:continue
  if key not in c.counts:raise ValueError('Missing contribution tooltip: '+key)
  days.append({**cell,'count':c.counts[key]})
 if not days or len(days)!=(today-date(today.year,1,1)).days+1:
  raise ValueError('Calendar is incomplete; retaining previous activity artwork')
 assert all(d['count']>=0 and 0<=d['level']<=4 for d in days)
 return {
  'as_of':today.isoformat(),'year':today.year,'username':USER,
  'contributions':sum(d['count'] for d in days),
  'public_repos':data['user']['public_repos'],
  'own_repo_stars':sum(r['stargazers_count'] for r in repos if not r['fork']),
  'npm':{'package':'gpu402','version':data['package']['version'],**data['downloads']},
  'days':sorted(days,key=lambda x:x['date']),
  'sources':urls}

def t(x,y,value,size=18,color=FG,weight=400,extra=''):
 return f'<text x="{x}" y="{y}" font-family="Arial, Helvetica, sans-serif" font-size="{size}" font-weight="{weight}" fill="{color}" {extra}>{escape(str(value))}</text>'

def render(d):
 b=f'<rect width="1200" height="357" rx="12" fill="{BG}"/>'
 b+=t(28,29,'GITHUB / NPM',11,CYAN,600,extra='letter-spacing="2"')
 b+=t(1171,29,'UPDATED '+d['as_of'],10,MUTED,extra='text-anchor="end" letter-spacing="1"')
 metrics=[(d['contributions'],str(d['year'])+' CONTRIBUTIONS'),(d['public_repos'],'PUBLIC REPOSITORIES'),(d['own_repo_stars'],'NON-FORK REPO STARS'),(d['npm']['downloads'],'gpu402 · 30D DOWNLOADS')]
 for i,(value,label) in enumerate(metrics):
  x=28+300*i
  b+=t(x,87,f'{value:,}',43,FG,600)+t(x,112,label,11,MUTED,extra='letter-spacing=".9"')
  if i<3:b+=f'<path d="M{x+265} 53V112" stroke="#244057"/>'
 b+='<path d="M28 133H1172" stroke="#244057"/>'
 # A shallow isometric calendar: every block maps to an actual day.
 colors=['#102b40','#185776','#258eae','#3dc0db','#91edfa']
 first=date(d['year'],1,1);offset=(first.weekday()+1)%7
 nweek=((date.fromisoformat(d['as_of'])-first).days+offset)//7+1
 dx=min(19.5,1020/max(nweek,1));startx=50
 for day in d['days']:
  dt=date.fromisoformat(day['date']);idx=(dt-first).days+offset
  week,row=divmod(idx,7);lev=day['level'];h=2+lev*7
  x=startx+week*dx+row*9.5;y=190+week*.78+row*9.0
  w=dx*.84;sy=4.9
  # Front and right faces make the data tangible while retaining legibility.
  b+=f'<g><title>{day["date"]}: {day["count"]} contributions</title>'
  b+=f'<path d="M{x:.2f} {y:.2f}l{w:.2f} {-sy:.2f}v{-h}l{-w:.2f} {sy:.2f}z" fill="#12364d"/>'
  b+=f'<path d="M{x+w:.2f} {y-sy:.2f}l{9:.2f} {5:.2f}v{-h}l-9 -5z" fill="#1c526e"/>'
  b+=f'<path d="M{x:.2f} {y-h:.2f}l{w:.2f} {-sy:.2f}l9 5l{-w:.2f} {sy:.2f}z" fill="{colors[lev]}" stroke="{BG}" stroke-width=".65"/></g>'
 for month in range(1,date.fromisoformat(d['as_of']).month+1):
  dt=date(d['year'],month,1);week=((dt-first).days+offset)//7
  x=startx+week*dx
  b+=t(x,297,dt.strftime('%b').upper(),9,MUTED)
 b+=t(28,333,'ONE BLOCK = ONE DAY',10,MUTED,extra='letter-spacing="1"')
 b+=t(1172,333,'npm window '+d['npm']['start']+' → '+d['npm']['end'],10,MUTED,extra='text-anchor="end"')
 svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="357" viewBox="0 0 1200 357" role="img" aria-labelledby="title"><title id="title">{d["year"]} GitHub contribution calendar and public GitHub/npm statistics for {USER}, refreshed {d["as_of"]}.</title>{b}</svg>\n'
 return svg

def render_mobile(d):
 b=f'<rect width="600" height="470" rx="12" fill="{BG}"/>'
 b+=t(24,30,'GITHUB / NPM',12,CYAN,600,extra='letter-spacing="2"')
 metrics=[(d['contributions'],str(d['year'])+' CONTRIBUTIONS'),(d['public_repos'],'PUBLIC REPOSITORIES'),(d['own_repo_stars'],'NON-FORK REPO STARS'),(d['npm']['downloads'],'gpu402 · 30D DOWNLOADS')]
 for i,(v,label) in enumerate(metrics):
  x=24+(i%2)*300;y=93+(i//2)*100
  b+=t(x,y,f'{v:,}',44,FG,600)+t(x,y+25,label,12,MUTED)
 b+='<path d="M24 237H576" stroke="#244057"/>'
 # Reuse the genuine daily columns from the desktop artwork.
 full=render(d)
 blocks=full[full.index('<g><title>'):full.index('<text',full.index('<g><title>'))]
 b+='<g transform="translate(0 155) scale(.49 .8)">'+blocks+'</g>'
 b+=t(24,421,'ONE BLOCK = ONE DAY',11,MUTED)
 b+=t(24,448,'UPDATED '+d['as_of']+' · npm: last-month window',11,MUTED)
 return f'<svg xmlns="http://www.w3.org/2000/svg" width="600" height="470" viewBox="0 0 600 470" role="img"><title>GitHub and npm activity for rythmern02, updated {d["as_of"]}</title>{b}</svg>\n'

def main():
 snapshot=OUT/'activity.json'
 d=json.loads(snapshot.read_text()) if '--offline' in sys.argv else collect(datetime.now(timezone.utc).date())
 svg=render(d)
 # Only mutate files after all sources and invariants have passed.
 OUT.mkdir(parents=True,exist_ok=True)
 if '--offline' not in sys.argv:snapshot.write_text(json.dumps(d,indent=2)+'\n')
 (OUT/'activity.svg').write_text(svg)
 (OUT/'activity-mobile.svg').write_text(render_mobile(d))
 print(f'Activity synced {d["as_of"]}: {d["contributions"]} contributions, {d["public_repos"]} repos, {d["own_repo_stars"]} stars, {d["npm"]["downloads"]} npm downloads.')
if __name__=='__main__':main()
