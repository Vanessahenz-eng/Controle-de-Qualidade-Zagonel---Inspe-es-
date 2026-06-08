import os, json, base64, requests
from flask import Flask, request, jsonify, Response
from datetime import datetime
import pandas as pd
from io import BytesIO

app = Flask(__name__)

DATA_FILE    = 'data.json'
UPLOAD_KEY   = os.environ.get('UPLOAD_KEY', 'zagonel2026')
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
GITHUB_REPO  = os.environ.get('GITHUB_REPO', '')

SETORES = {
    'B2-03':   {'nome': 'Apoio B2-03', 'cor': '#2563EB', 'colaboradores': {'Juliana': 30, 'Sirlei': 30, 'Danmari': 29}, 'campos_executor': ['Executor', 'Executor do teste']},
    'B1-01':   {'nome': 'Apoio B1-01', 'cor': '#059669', 'colaboradores': {'Luana': 28, 'Bruna': 27},                   'campos_executor': ['Responsável pela conferência', 'Executor', 'Executor do teste']},
    'Injecao': {'nome': 'Injeção',     'cor': '#7C3AED', 'colaboradores': {},                                           'campos_executor': ['Executor', 'Executor do teste'], 'meta_padrao': 15, 'metas_fixas': {'jocemar': 20, 'kaue': 18}},
}

def load_data():
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE) as f: return json.load(f)
    except: pass
    if GITHUB_TOKEN and GITHUB_REPO:
        try:
            r = requests.get(f'https://api.github.com/repos/{GITHUB_REPO}/contents/data.json', headers={'Authorization': f'token {GITHUB_TOKEN}'}, timeout=5)
            if r.status_code == 200: return json.loads(base64.b64decode(r.json()['content']).decode())
        except: pass
    return {'B2-03': {}, 'B1-01': {}, 'Injecao': {}}

def save_data(data):
    try:
        with open(DATA_FILE, 'w') as f: json.dump(data, f, ensure_ascii=False, default=str)
    except: pass
    if GITHUB_TOKEN and GITHUB_REPO:
        try:
            content = base64.b64encode(json.dumps(data, ensure_ascii=False, default=str).encode()).decode()
            r = requests.get(f'https://api.github.com/repos/{GITHUB_REPO}/contents/data.json', headers={'Authorization': f'token {GITHUB_TOKEN}'}, timeout=5)
            sha = r.json().get('sha', '') if r.status_code == 200 else ''
            payload = {'message': f'update {datetime.now().strftime("%Y-%m-%d %H:%M")}', 'content': content}
            if sha: payload['sha'] = sha
            requests.put(f'https://api.github.com/repos/{GITHUB_REPO}/contents/data.json', headers={'Authorization': f'token {GITHUB_TOKEN}'}, json=payload, timeout=10)
        except: pass

def norm_name(n, setor_key):
    if not n: return None
    s = str(n).strip()
    for nome in SETORES[setor_key].get('colaboradores', {}):
        if nome.lower() in s.lower(): return nome
    if setor_key == 'Injecao' and len(s) > 3: return s.title()
    return None

def get_meta(nome, setor_key):
    setor = SETORES[setor_key]
    if setor_key == 'Injecao':
        k = nome.lower().replace('ê','e')
        for chave, meta in setor.get('metas_fixas', {}).items():
            if chave in k: return meta
        return setor.get('meta_padrao', 15)
    return setor['colaboradores'].get(nome, 0)

def parse_xlsx(file_bytes, setor_key):
    try: df = pd.read_excel(BytesIO(file_bytes))
    except Exception as e: return None, None, str(e)
    campos_exec = SETORES[setor_key]['campos_executor']
    by_code = {}
    for _, row in df.iterrows():
        cod = row.get('Código da avaliação')
        if cod is None or (isinstance(cod, float) and pd.isna(cod)): continue
        cod = str(cod)
        if cod not in by_code: by_code[cod] = {'at': None, 'ex': None, 'cf': None, 'ini': None, 'fim': None}
        item = str(row.get('Item', '') or '').strip()
        resp = str(row.get('Resposta', '') or '').strip()
        if item == 'Confirme aqui o nome da máquina ou atividade': by_code[cod]['at'] = resp
        if item in campos_exec:
            n = norm_name(resp, setor_key)
            if n: by_code[cod]['ex'] = n
        if item == 'Todos os itens avaliados apresentaram-se conformes?': by_code[cod]['cf'] = resp
        ini = row.get('Data inicial'); fim = row.get('Data final')
        if not by_code[cod]['ini'] and ini is not None and str(ini) not in ('', 'nan'): by_code[cod]['ini'] = ini
        if fim is not None and str(fim) not in ('', 'nan'): by_code[cod]['fim'] = fim
    inspecoes = []
    for o in by_code.values():
        if not o['ex'] or not o['at']: continue
        try:
            ini = pd.to_datetime(o['ini'], dayfirst=True) if o['ini'] is not None else None
            fim = pd.to_datetime(o['fim'], dayfirst=True) if o['fim'] is not None else None
            dur = round((fim - ini).total_seconds() / 60, 2) if ini and fim and fim > ini else None
            inspecoes.append({'at': o['at'], 'ex': o['ex'], 'cf': o['cf'], 'ini': ini.strftime('%Y-%m-%dT%H:%M:%S') if ini else None, 'fim': fim.strftime('%Y-%m-%dT%H:%M:%S') if fim else None, 'dur': dur})
        except: continue
    if not inspecoes: return None, None, 'Nenhuma inspeção encontrada'
    ref = next((i['ini'] for i in inspecoes if i['ini']), None)
    if not ref: return None, None, 'Datas não encontradas'
    data_key = ref[:10]
    colaboradores = {}
    for ins in inspecoes:
        p = ins['ex']
        if p not in colaboradores: colaboradores[p] = {'meta': get_meta(p, setor_key), 'total': 0, 'nc': 0, 'teste': 0, 'inspecoes': []}
        colaboradores[p]['total'] += 1
        if ins['cf'] == 'Não': colaboradores[p]['nc'] += 1
        if not ins['cf']: colaboradores[p]['teste'] += 1
        colaboradores[p]['inspecoes'].append({'at': ins['at'], 'cf': ins['cf'], 'ini': ins['ini'], 'fim': ins['fim'], 'dur': ins['dur']})
    return data_key, colaboradores, None

@app.route('/api/data')
def api_data(): return jsonify(load_data())

@app.route('/api/upload', methods=['POST'])
def api_upload():
    if request.form.get('key') != UPLOAD_KEY: return jsonify({'error': 'Senha incorreta'}), 401
    setor = request.form.get('setor')
    if setor not in SETORES: return jsonify({'error': 'Setor invalido'}), 400
    file = request.files.get('file')
    if not file: return jsonify({'error': 'Arquivo nao enviado'}), 400
    data_key, colaboradores, err = parse_xlsx(file.read(), setor)
    if err: return jsonify({'error': err}), 400
    db = load_data()
    if setor not in db: db[setor] = {}
    db[setor][data_key] = colaboradores
    save_data(db)
    d = datetime.strptime(data_key, '%Y-%m-%d')
    return jsonify({'ok': True, 'data': d.strftime('%d/%m/%Y'), 'setor': SETORES[setor]['nome'], 'colaboradores': list(colaboradores.keys())})

@app.route('/api/delete', methods=['POST'])
def api_delete():
    data = request.get_json() or {}
    if data.get('key') != UPLOAD_KEY: return jsonify({'error': 'Senha incorreta'}), 401
    setor, dk = data.get('setor'), data.get('data')
    db = load_data()
    if setor in db and dk in db[setor]: del db[setor][dk]; save_data(db)
    return jsonify({'ok': True})

@app.route('/')
def index(): return Response(get_html(), mimetype='text/html')

def get_html():
    return '''<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Controle de Inspecoes - Zagonel</title>
<style>
:root{--bg:#F0F4F8;--wh:#fff;--bd:#E2E8F0;--tx:#1A202C;--mu:#718096;--gr:#059669;--am:#D97706;--rd:#DC2626;--gr2:#ECFDF5;--am2:#FFFBEB;--rd2:#FEF2F2}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;background:var(--bg);color:var(--tx);min-height:100vh}
.top{background:#05B15D;color:#fff;padding:.85rem 1.5rem;display:flex;justify-content:space-between;align-items:center}
.top h1{font-size:18px;font-weight:700}
.top p{font-size:11px;opacity:.85;margin-top:2px}
.main{max-width:1200px;margin:0 auto;padding:1.5rem}
.tabs{display:flex;gap:8px;margin-bottom:1.5rem;flex-wrap:wrap;align-items:center}
.tab{padding:8px 18px;border-radius:8px;font-size:13px;font-weight:500;cursor:pointer;border:1.5px solid var(--bd);background:var(--wh);color:var(--mu)}
.tab.on{color:#fff;border-color:transparent}
#tt.on{background:#334155}#tb1.on{background:#2563EB}#tb2.on{background:#059669}#tb3.on{background:#7C3AED}#ti.on{background:#05B15D}
.pg{display:none}.pg.on{display:block}
.kg{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:12px;margin-bottom:1.5rem}
.kc{background:var(--wh);border:1px solid var(--bd);border-radius:10px;padding:14px 16px}
.kl{font-size:11px;color:var(--mu);text-transform:uppercase;letter-spacing:.05em;margin-bottom:.35rem}
.kv{font-size:26px;font-weight:700}
.ks{font-size:11px;color:var(--mu);margin-top:.2rem}
.cg{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px;margin-bottom:1.5rem}
.card{background:var(--wh);border:1px solid var(--bd);border-radius:12px;padding:1.25rem;position:relative;overflow:hidden}
.card::before{content:"";position:absolute;top:0;left:0;right:0;height:4px;border-radius:12px 12px 0 0}
.sv::before{background:var(--gr)}.at::before{background:var(--am)}.no::before{background:var(--rd)}.em::before{background:var(--bd)}
.cn{font-size:11px;font-weight:700;color:var(--mu);text-transform:uppercase;letter-spacing:.06em;margin-bottom:.2rem}
.cm{font-size:11px;color:var(--mu);margin-bottom:.75rem}
.cp{font-size:44px;font-weight:700;line-height:1;margin-bottom:.2rem}
.sv .cp{color:var(--gr)}.at .cp{color:var(--am)}.no .cp{color:var(--rd)}.em .cp{color:#CBD5E0}
.cs{font-size:12px;color:var(--mu);margin-bottom:.75rem}
.bar{height:5px;background:#EDF2F7;border-radius:3px;margin-bottom:1rem;overflow:hidden}
.bf{height:5px;border-radius:3px}
.sv .bf{background:var(--gr)}.at .bf{background:var(--am)}.no .bf{background:var(--rd)}.em .bf{background:#CBD5E0}
.cst{display:grid;grid-template-columns:repeat(3,1fr);border-top:1px solid var(--bd);padding-top:.75rem}
.cv{font-size:18px;font-weight:700;text-align:center}
.cl2{font-size:10px;color:var(--mu);text-align:center;margin-top:2px}
.pill{display:inline-flex;align-items:center;gap:4px;font-size:11px;font-weight:600;padding:3px 10px;border-radius:20px;margin-top:.6rem}
.sv .pill{background:var(--gr2);color:var(--gr)}.at .pill{background:var(--am2);color:var(--am)}.no .pill{background:var(--rd2);color:var(--rd)}.em .pill{background:#F7FAFC;color:var(--mu)}
.nc{display:flex;justify-content:space-between;font-size:11px;border-top:1px solid var(--bd);padding-top:.5rem;margin-top:.5rem}
.nb{color:var(--rd);font-weight:700}.ng{color:var(--gr);font-weight:700}
.dsel{display:flex;align-items:center;gap:10px;margin-bottom:1.25rem}
.dsel select{flex:1;padding:8px 12px;border:1px solid var(--bd);border-radius:8px;font-size:13px;background:var(--wh);color:var(--tx);font-family:inherit}
.sl{font-size:11px;font-weight:700;color:var(--mu);text-transform:uppercase;letter-spacing:.06em;margin-bottom:.75rem}
.tw{background:var(--wh);border:1px solid var(--bd);border-radius:10px;overflow:hidden;margin-bottom:1.25rem}
table{width:100%;border-collapse:collapse;font-size:12px;table-layout:fixed}
th{background:#F7FAFC;padding:9px 12px;text-align:left;font-size:10px;font-weight:700;color:var(--mu);text-transform:uppercase;letter-spacing:.05em;border-bottom:1px solid var(--bd)}
td{padding:8px 12px;border-bottom:1px solid var(--bd);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
tr:last-child td{border-bottom:none}tr:nth-child(even) td{background:#FAFAFA}
.tag{display:inline-block;padding:2px 8px;border-radius:4px;font-size:10px;font-weight:600}
.tok{background:#ECFDF5;color:#065F46}.tnc{background:#FEF2F2;color:#991B1B}.tts{background:#FFFBEB;color:#92400E}
.div{border:none;border-top:1px solid var(--bd);margin:1.25rem 0}
.sb{margin-bottom:2rem}
.sh{display:flex;align-items:center;gap:8px;margin-bottom:1rem}
.sd{width:12px;height:12px;border-radius:3px}
.st{font-size:16px;font-weight:700}
.ss{font-size:12px;color:var(--mu);margin-left:auto}
.uf{background:var(--wh);border:1px solid var(--bd);border-radius:12px;padding:1.5rem;max-width:520px}
.uf h3{font-size:16px;font-weight:700;margin-bottom:1rem}
.fg{margin-bottom:1rem}
.fg label{display:block;font-size:11px;font-weight:700;color:var(--mu);text-transform:uppercase;letter-spacing:.04em;margin-bottom:.35rem}
.fg input,.fg select{width:100%;padding:9px 12px;border:1px solid var(--bd);border-radius:8px;font-size:13px;font-family:inherit;background:var(--wh);color:var(--tx)}
.ub{width:100%;padding:11px;background:#05B15D;color:#fff;border:none;border-radius:8px;font-size:14px;font-weight:700;cursor:pointer;font-family:inherit}
.ub:hover{background:#047a42}.ub:disabled{opacity:.6;cursor:not-allowed}
.msg{padding:10px 14px;border-radius:8px;font-size:13px;margin-top:.75rem}
.mok{background:var(--gr2);color:#065F46}.merr{background:var(--rd2);color:#991B1B}
.db{font-size:11px;color:var(--rd);background:none;border:1px solid #FCA5A5;border-radius:4px;padding:3px 10px;cursor:pointer}
.empty{text-align:center;padding:3rem;color:var(--mu);font-size:13px}
</style>
</head>
<body>
<div class="top">
  <div><h1>Controle de Inspecoes</h1><p>Zagonel - Qualidade Industrial</p></div>
  <div id="nfo" style="font-size:12px;opacity:.8">Carregando...</div>
</div>
<div class="main">
  <div class="tabs">
    <button class="tab on" id="tt" onclick="gt(0)">Todos os setores</button>
    <button class="tab" id="tb1" onclick="gt(1)">Apoio B2-03</button>
    <button class="tab" id="tb2" onclick="gt(2)">Apoio B1-01</button>
    <button class="tab" id="tb3" onclick="gt(3)">Injecao</button>
    <button class="tab" id="ti" onclick="gt(4)" style="margin-left:auto">Importar</button>
  </div>
  <div id="p0" class="pg on"><div id="c0"><div class="empty">Carregando...</div></div></div>
  <div id="p1" class="pg"><div id="c1"><div class="empty">Sem dados.</div></div></div>
  <div id="p2" class="pg"><div id="c2"><div class="empty">Sem dados.</div></div></div>
  <div id="p3" class="pg"><div id="c3"><div class="empty">Sem dados.</div></div></div>
  <div id="p4" class="pg">
    <div class="uf">
      <h3>Importar planilha diaria</h3>
      <div class="fg"><label>Setor</label>
        <select id="us">
          <option value="B2-03">Apoio B2-03</option>
          <option value="B1-01">Apoio B1-01</option>
          <option value="Injecao">Injecao</option>
        </select>
      </div>
      <div class="fg"><label>Arquivo .xlsx</label><input type="file" id="uf2" accept=".xlsx"></div>
      <div class="fg"><label>Senha</label><input type="password" id="uk" placeholder="senha"></div>
      <button class="ub" id="ubtn" onclick="doUp()">Importar dados</button>
      <div class="msg" id="umsg" style="display:none"></div>
    </div>
    <div id="dl" style="margin-top:1.5rem"></div>
  </div>
</div>
<script>
var DB = {};
var SK = ['B2-03','B1-01','Injecao'];
var SN = {'B2-03':'Apoio B2-03','B1-01':'Apoio B1-01','Injecao':'Injecao'};
var SC = {'B2-03':'#2563EB','B1-01':'#059669','Injecao':'#7C3AED'};
var TIDS = ['tt','tb1','tb2','tb3','ti'];

function gt(n) {
  TIDS.forEach(function(id){ document.getElementById(id).classList.remove('on'); });
  document.getElementById(TIDS[n]).classList.add('on');
  for(var i=0;i<=4;i++) document.getElementById('p'+i).classList.remove('on');
  document.getElementById('p'+n).classList.add('on');
  if(n===0) rAll();
  else if(n>=1 && n<=3) rS(SK[n-1],n);
  else rDL();
}

function fD(k){ var d=new Date(k+'T12:00:00'); return pad(d.getDate())+'/'+pad(d.getMonth()+1)+'/'+d.getFullYear(); }
function fT(s){ if(!s)return'--'; var d=new Date(s); return pad(d.getHours())+':'+pad(d.getMinutes()); }
function pad(n){ return n<10?'0'+n:''+n; }
function fDur(m){ if(m==null||isNaN(m))return'--'; return Math.floor(m)+'min '+pad(Math.round((m-Math.floor(m))*60))+'s'; }
function cl(p,t){ if(!t)return'em'; if(p<85)return'no'; if(p<=100)return'at'; return'sv'; }
function pt(c){ return c==='sv'?'Superou':c==='at'?'Atingiu a meta':c==='no'?'Nao atingiu':'Sem dados'; }

function bCard(nome,d){
  var tot=d.total||0,meta=d.meta||0,nc=d.nc||0;
  var pct=meta>0?Math.round(tot/meta*100):0,c=cl(pct,tot);
  var h='<div class="card '+c+'">';
  h+='<div class="cn">'+nome+'</div>';
  h+='<div class="cm">Meta: '+meta+' inspecoes/dia</div>';
  h+='<div class="cp">'+(!tot?'--':pct+'%')+'</div>';
  h+='<div class="cs">'+(!tot?'Sem registros':tot+' realizadas - meta '+meta)+'</div>';
  h+='<div class="bar"><div class="bf" style="width:'+(!tot?0:Math.min(pct,100))+'%"></div></div>';
  h+='<div class="cst"><div><div class="cv">'+tot+'</div><div class="cl2">realizadas</div></div>';
  h+='<div><div class="cv">'+(tot-nc)+'</div><div class="cl2">conformes</div></div>';
  h+='<div><div class="cv">'+meta+'</div><div class="cl2">meta</div></div></div>';
  h+='<span class="pill">'+pt(c)+'</span>';
  h+='<div class="nc"><span style="color:var(--mu)">NCs</span><span class="'+(nc>0?'nb':'ng')+'">'+nc+' NC'+(nc!==1?'s':'')+'</span></div></div>';
  return h;
}

function bSetor(sk,dk){
  var sd=(DB[sk]||{})[dk]||{};
  var col=Object.keys(sd);
  if(!col.length)return'<div class="empty">Sem dados para '+SN[sk]+' neste dia.</div>';
  var tot=0,meta=0,nc=0,nsv=0,nat=0,nno=0;
  col.forEach(function(n){ var d=sd[n]; tot+=d.total; if(d.total>0)meta+=d.meta; nc+=d.nc; var p=d.meta>0?Math.round(d.total/d.meta*100):0,c=cl(p,d.total); if(c==='sv')nsv++;else if(c==='at')nat++;else if(c==='no')nno++; });
  var pct=meta>0?Math.round(tot/meta*100):0;
  var cor=SC[sk]||'#334155';
  var h='<div class="sb"><div class="sh"><div class="sd" style="background:'+cor+'"></div><div class="st">'+SN[sk]+'</div><div class="ss">'+tot+' insp - '+pct+'% meta - '+nc+' NCs</div></div>';
  h+='<div class="kg">';
  h+='<div class="kc"><div class="kl">Inspecoes</div><div class="kv">'+tot+'</div><div class="ks">meta: '+meta+'</div></div>';
  h+='<div class="kc"><div class="kl">% da meta</div><div class="kv" style="color:'+(pct>=100?'var(--gr)':pct>=85?'var(--am)':'var(--rd)')+'">'+pct+'%</div></div>';
  h+='<div class="kc"><div class="kl">Status</div><div class="kv" style="font-size:13px;line-height:1.8">';
  if(nsv>0)h+='<span style="color:var(--gr)">'+nsv+' superou</span><br>';
  if(nat>0)h+='<span style="color:var(--am)">'+nat+' atingiu</span><br>';
  if(nno>0)h+='<span style="color:var(--rd)">'+nno+' abaixo</span>';
  h+='</div></div></div><div class="cg">';
  col.forEach(function(n){ h+=bCard(n,sd[n]); });
  h+='</div></div>';
  return h;
}

function rAll(){
  var el=document.getElementById('c0');
  var dias=[];
  SK.forEach(function(sk){ Object.keys(DB[sk]||{}).forEach(function(d){ if(dias.indexOf(d)<0)dias.push(d); }); });
  dias.sort(function(a,b){ return b.localeCompare(a); });
  if(!dias.length){ el.innerHTML='<div class="empty">Nenhum dado importado. Va em Importar para comecar.</div>'; return; }
  var sel=document.createElement('div');
  sel.className='dsel';
  var lbl=document.createElement('span');
  lbl.className='sl'; lbl.style.margin='0'; lbl.style.whiteSpace='nowrap'; lbl.textContent='Data';
  var s=document.createElement('select');
  s.id='s0';
  dias.forEach(function(d,i){ var o=document.createElement('option'); o.value=d; o.textContent=fD(d); if(i===0)o.selected=true; s.appendChild(o); });
  sel.appendChild(lbl); sel.appendChild(s);
  var body=document.createElement('div'); body.id='b0';
  el.innerHTML=''; el.appendChild(sel); el.appendChild(body);
  s.addEventListener('change', rAllDay);
  rAllDay();
}

function rAllDay(){
  var sel=document.getElementById('s0'); if(!sel)return;
  var dk=sel.value; var h='';
  SK.forEach(function(sk){ h+=bSetor(sk,dk); });
  document.getElementById('b0').innerHTML=h;
}

function rS(sk,n){
  var el=document.getElementById('c'+n); if(!el)return;
  var dias=Object.keys(DB[sk]||{}).sort(function(a,b){ return b.localeCompare(a); });
  if(!dias.length){ el.innerHTML='<div class="empty">Sem dados. Importe uma planilha.</div>'; return; }
  var sel=document.createElement('div'); sel.className='dsel';
  var lbl=document.createElement('span'); lbl.className='sl'; lbl.style.margin='0'; lbl.style.whiteSpace='nowrap'; lbl.textContent='Data';
  var s=document.createElement('select'); s.id='s'+n;
  dias.forEach(function(d,i){ var o=document.createElement('option'); o.value=d; o.textContent=fD(d); if(i===0)o.selected=true; s.appendChild(o); });
  sel.appendChild(lbl); sel.appendChild(s);
  var body=document.createElement('div'); body.id='b'+n;
  el.innerHTML=''; el.appendChild(sel); el.appendChild(body);
  s.addEventListener('change', function(){ rSDay(sk,n); });
  rSDay(sk,n);
}

function rSDay(sk,n){
  var sel=document.getElementById('s'+n); if(!sel)return;
  var dk=sel.value;
  var sd=(DB[sk]||{})[dk]||{};
  var h=bSetor(sk,dk);
  Object.keys(sd).forEach(function(nome){
    var d=sd[nome];
    if(!d.inspecoes||!d.inspecoes.length)return;
    h+='<div class="div"></div><div class="sl">'+nome+' - '+d.total+' inspecoes</div>';
    h+='<div class="tw"><table><thead><tr><th style="width:24px">#</th><th>Atividade</th><th style="width:55px">Inicio</th><th style="width:55px">Fim</th><th style="width:75px">Duracao</th><th style="width:75px">Status</th></tr></thead><tbody>';
    d.inspecoes.forEach(function(ins,i){
      var nc=ins.cf==='Nao',te=!ins.cf;
      var tag=nc?'<span class="tag tnc">NC</span>':te?'<span class="tag tts">Teste</span>':'<span class="tag tok">OK</span>';
      h+='<tr><td>'+(i+1)+'</td><td>'+(ins.at||'--')+'</td><td>'+fT(ins.ini)+'</td><td>'+fT(ins.fim)+'</td><td>'+fDur(ins.dur)+'</td><td>'+tag+'</td></tr>';
    });
    h+='</tbody></table></div>';
  });
  document.getElementById('b'+n).innerHTML=h;
}

function rDL(){
  var el=document.getElementById('dl'); if(!el)return;
  var itens=[];
  SK.forEach(function(sk){ Object.keys(DB[sk]||{}).forEach(function(dk){ var col=DB[sk][dk]; itens.push({sk:sk,dk:dk,tot:Object.keys(col).reduce(function(a,n){return a+col[n].total;},0),nc:Object.keys(col).reduce(function(a,n){return a+col[n].nc;},0),nomes:Object.keys(col)}); }); });
  itens.sort(function(a,b){ return b.dk.localeCompare(a.dk); });
  if(!itens.length){ el.innerHTML=''; return; }
  var h='<div class="sl">Dias importados</div><div class="tw"><table><thead><tr><th>Setor</th><th>Data</th><th>Colaboradores</th><th>Total</th><th>NCs</th><th></th></tr></thead><tbody>';
  itens.forEach(function(it){
    h+='<tr><td style="font-weight:700;color:'+SC[it.sk]+'">'+SN[it.sk]+'</td>';
    h+='<td style="font-weight:600">'+fD(it.dk)+'</td>';
    h+='<td style="font-size:11px;color:var(--mu)">'+it.nomes.join(', ')+'</td>';
    h+='<td>'+it.tot+'</td>';
    h+='<td>'+(it.nc>0?'<span class="tag tnc">'+it.nc+'</span>':'<span class="tag tok">0</span>')+'</td>';
    h+='<td><button class="db" data-sk="'+it.sk+'" data-dk="'+it.dk+'">Remover</button></td></tr>';
  });
  h+='</tbody></table></div>';
  el.innerHTML=h;
  el.querySelectorAll('.db').forEach(function(btn){
    btn.addEventListener('click', function(){
      delDay(this.getAttribute('data-sk'), this.getAttribute('data-dk'));
    });
  });
}

async function doUp(){
  var setor=document.getElementById('us').value;
  var file=document.getElementById('uf2').files[0];
  var key=document.getElementById('uk').value;
  var btn=document.getElementById('ubtn');
  var msg=document.getElementById('umsg');
  msg.style.display='none';
  if(!file){msg.textContent='Selecione um arquivo .xlsx';msg.className='msg merr';msg.style.display='block';return;}
  if(!key){msg.textContent='Digite a senha';msg.className='msg merr';msg.style.display='block';return;}
  btn.disabled=true;btn.textContent='Importando...';
  var fd=new FormData();
  fd.append('setor',setor);fd.append('file',file);fd.append('key',key);
  try{
    var r=await fetch('/api/upload',{method:'POST',body:fd});
    var d=await r.json();
    if(d.ok){
      msg.textContent='OK - Dia '+d.data+' importado - '+d.setor+' - '+d.colaboradores.join(', ');
      msg.className='msg mok';msg.style.display='block';
      document.getElementById('uf2').value='';
      await loadDB();rDL();
    }else{msg.textContent=d.error||'Erro';msg.className='msg merr';msg.style.display='block';}
  }catch(e){msg.textContent='Erro: '+e.message;msg.className='msg merr';msg.style.display='block';}
  btn.disabled=false;btn.textContent='Importar dados';
}

async function delDay(sk,dk){
  if(!confirm('Remover '+SN[sk]+' - '+fD(dk)+'?'))return;
  var key=prompt('Senha:');if(!key)return;
  await fetch('/api/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({setor:sk,data:dk,key:key})});
  await loadDB();rDL();
}

async function loadDB(){
  try{
    var r=await fetch('/api/data');DB=await r.json();
    var n=SK.reduce(function(a,sk){return a+Object.keys(DB[sk]||{}).length;},0);
    document.getElementById('nfo').textContent=n+' dias registrados';
    rAll();
  }catch(e){document.getElementById('nfo').textContent='Erro ao carregar';}
}

loadDB();
</script>
</body>
</html>'''

if __name__ == '__main__':
    app.run(debug=True)
