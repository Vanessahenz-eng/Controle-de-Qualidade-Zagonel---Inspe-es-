import os, json, base64, requests
from flask import Flask, request, jsonify, render_template_string
from datetime import datetime
import pandas as pd
from io import BytesIO

app = Flask(__name__)

# ── Configurações ──────────────────────────────────────────────
DATA_FILE   = '/data/data.json'
UPLOAD_KEY  = os.environ.get('UPLOAD_KEY', 'zagonel2026')
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
GITHUB_REPO  = os.environ.get('GITHUB_REPO', '')  # ex: "usuario/zagonel-inspecoes"

# ── Metas por setor ─────────────────────────────────────────────
SETORES = {
    'B2-03': {
        'nome': 'Apoio B2-03',
        'cor': '#2563EB',
        'colaboradores': {
            'Juliana': {'meta': 30, 'turno': '05:20–15:08'},
            'Sirlei':  {'meta': 30, 'turno': '05:20–15:08'},
            'Danmari': {'meta': 29, 'turno': '15:00–00:27'},
        },
        'campos_executor': ['Executor', 'Executor do teste'],
    },
    'B1-01': {
        'nome': 'Apoio B1-01',
        'cor': '#059669',
        'colaboradores': {
            'Luana': {'meta': 28, 'turno': '05:20–15:08'},
            'Bruna': {'meta': 27, 'turno': '15:00–00:27'},
        },
        'campos_executor': ['Responsável pela conferência', 'Executor', 'Executor do teste'],
    },
    'Injecao': {
        'nome': 'Injeção',
        'cor': '#7C3AED',
        'colaboradores': {},  # dinâmico
        'campos_executor': ['Executor', 'Executor do teste'],
        'meta_padrao': 15,
        'metas_fixas': {'jocemar': 20, 'kaue': 18, 'kauê': 18},
    },
}

FALLBACK_DATA = {}

# ── Persistência ────────────────────────────────────────────────
def load_data():
    # 1. Disco local
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE) as f:
                return json.load(f)
        except: pass
    # 2. GitHub
    if GITHUB_TOKEN and GITHUB_REPO:
        try:
            r = requests.get(
                f'https://api.github.com/repos/{GITHUB_REPO}/contents/data.json',
                headers={'Authorization': f'token {GITHUB_TOKEN}'}, timeout=5)
            if r.status_code == 200:
                content = base64.b64decode(r.json()['content']).decode()
                return json.loads(content)
        except: pass
    # 3. Fallback
    return FALLBACK_DATA.copy() or {'B2-03': {}, 'B1-01': {}, 'Injecao': {}}

def save_data(data):
    # Disco
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, ensure_ascii=False, default=str)
    # GitHub
    if GITHUB_TOKEN and GITHUB_REPO:
        try:
            content = base64.b64encode(json.dumps(data, ensure_ascii=False, default=str).encode()).decode()
            r = requests.get(
                f'https://api.github.com/repos/{GITHUB_REPO}/contents/data.json',
                headers={'Authorization': f'token {GITHUB_TOKEN}'}, timeout=5)
            sha = r.json().get('sha', '') if r.status_code == 200 else ''
            payload = {'message': f'update data {datetime.now().strftime("%Y-%m-%d %H:%M")}',
                       'content': content}
            if sha: payload['sha'] = sha
            requests.put(
                f'https://api.github.com/repos/{GITHUB_REPO}/contents/data.json',
                headers={'Authorization': f'token {GITHUB_TOKEN}'},
                json=payload, timeout=10)
        except: pass

# ── Processamento xlsx ───────────────────────────────────────────
def norm_name(n, setor_key):
    if not n: return None
    s = str(n).strip()
    setor = SETORES[setor_key]
    # Checar colaboradores conhecidos
    for nome in setor['colaboradores']:
        if nome.lower() in s.lower():
            return nome
    # Injeção: qualquer nome válido
    if setor_key == 'Injecao' and len(s) > 3:
        return s.title()
    return None

def get_meta_injecao(nome):
    k = nome.lower().replace('ê','e').replace('á','a').replace('ã','a')
    metas_fixas = SETORES['Injecao']['metas_fixas']
    for chave, meta in metas_fixas.items():
        if chave in k:
            return meta
    return SETORES['Injecao']['meta_padrao']

def parse_xlsx(file_bytes, setor_key):
    df = pd.read_excel(BytesIO(file_bytes))
    setor = SETORES[setor_key]
    campos_exec = setor['campos_executor']

    by_code = {}
    for _, row in df.iterrows():
        cod = row.get('Código da avaliação')
        if not cod: continue
        if cod not in by_code:
            by_code[cod] = {'at': None, 'ex': None, 'cf': None, 'ini': None, 'fim': None}
        item = str(row.get('Item', '') or '').strip()
        resp = str(row.get('Resposta', '') or '').strip()
        if item == 'Confirme aqui o nome da máquina ou atividade':
            by_code[cod]['at'] = resp
        if item in campos_exec:
            n = norm_name(resp, setor_key)
            if n: by_code[cod]['ex'] = n
        if item == 'Todos os itens avaliados apresentaram-se conformes?':
            by_code[cod]['cf'] = resp
        if not by_code[cod]['ini'] and row.get('Data inicial'):
            by_code[cod]['ini'] = row['Data inicial']
        if row.get('Data final'):
            by_code[cod]['fim'] = row['Data final']

    inspecoes = []
    for o in by_code.values():
        if not o['ex'] or not o['at']: continue
        try:
            ini = pd.to_datetime(o['ini'], dayfirst=True) if o['ini'] else None
            fim = pd.to_datetime(o['fim'], dayfirst=True) if o['fim'] else None
            dur = round((fim - ini).total_seconds() / 60, 2) if ini and fim and fim > ini else None
            inspecoes.append({
                'at': o['at'], 'ex': o['ex'], 'cf': o['cf'],
                'ini': ini.strftime('%Y-%m-%dT%H:%M:%S') if ini else None,
                'fim': fim.strftime('%Y-%m-%dT%H:%M:%S') if fim else None,
                'dur': dur
            })
        except: continue

    if not inspecoes: return None, None
    ref = next((i['ini'] for i in inspecoes if i['ini']), None)
    if not ref: return None, None
    data_key = ref[:10]  # YYYY-MM-DD

    # Agregar por colaborador
    colaboradores = {}
    for ins in inspecoes:
        p = ins['ex']
        if p not in colaboradores:
            meta = (get_meta_injecao(p) if setor_key == 'Injecao'
                    else setor['colaboradores'].get(p, {}).get('meta', 0))
            colaboradores[p] = {'meta': meta, 'total': 0, 'nc': 0, 'teste': 0, 'inspecoes': []}
        colaboradores[p]['total'] += 1
        if ins['cf'] == 'Não': colaboradores[p]['nc'] += 1
        if not ins['cf']: colaboradores[p]['teste'] += 1
        colaboradores[p]['inspecoes'].append({
            'at': ins['at'], 'cf': ins['cf'],
            'ini': ins['ini'], 'fim': ins['fim'], 'dur': ins['dur']
        })

    return data_key, colaboradores

# ── Rotas API ────────────────────────────────────────────────────
@app.route('/api/data')
def api_data():
    return jsonify(load_data())

@app.route('/api/upload', methods=['POST'])
def api_upload():
    if request.form.get('key') != UPLOAD_KEY:
        return jsonify({'error': 'Chave incorreta'}), 401
    setor = request.form.get('setor')
    if setor not in SETORES:
        return jsonify({'error': 'Setor inválido'}), 400
    file = request.files.get('file')
    if not file:
        return jsonify({'error': 'Arquivo não enviado'}), 400

    data_key, colaboradores = parse_xlsx(file.read(), setor)
    if not data_key:
        return jsonify({'error': 'Nenhuma inspeção encontrada'}), 400

    db = load_data()
    if setor not in db: db[setor] = {}
    db[setor][data_key] = colaboradores
    save_data(db)

    d = datetime.strptime(data_key, '%Y-%m-%d')
    label = d.strftime('%d/%m/%Y')
    return jsonify({'ok': True, 'data': label, 'setor': SETORES[setor]['nome'],
                    'colaboradores': list(colaboradores.keys())})

@app.route('/api/delete', methods=['POST'])
def api_delete():
    if request.json.get('key') != UPLOAD_KEY:
        return jsonify({'error': 'Chave incorreta'}), 401
    setor = request.json.get('setor')
    data = request.json.get('data')
    db = load_data()
    if setor in db and data in db[setor]:
        del db[setor][data]
        save_data(db)
    return jsonify({'ok': True})

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE,
        setores=json.dumps({k: v['nome'] for k, v in SETORES.items()}),
        cores=json.dumps({k: v['cor'] for k, v in SETORES.items()}))

# ── Template HTML ─────────────────────────────────────────────────
HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Controle de Inspeções — Zagonel</title>
<style>
:root{--bg:#F0F4F8;--white:#FFFFFF;--border:#E2E8F0;--text:#1A202C;--muted:#718096;
  --green:#059669;--amber:#D97706;--red:#DC2626;--green-bg:#ECFDF5;--amber-bg:#FFFBEB;--red-bg:#FEF2F2;
  --b203:#2563EB;--b101:#059669;--inj:#7C3AED}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:var(--bg);color:var(--text);min-height:100vh}
.header{background:#05B15D;color:white;padding:1rem 1.5rem;display:flex;justify-content:space-between;align-items:center}
.header-left h1{font-size:20px;font-weight:700;margin-bottom:2px}
.header-left p{font-size:12px;opacity:.85}
.header-right{font-size:12px;opacity:.8;text-align:right}
.main{max-width:1200px;margin:0 auto;padding:1.5rem}
.sector-tabs{display:flex;gap:8px;margin-bottom:1.5rem;flex-wrap:wrap}
.stab{padding:8px 18px;border-radius:8px;font-size:13px;font-weight:500;cursor:pointer;border:2px solid transparent;background:var(--white);color:var(--muted);transition:.15s}
.stab.active{color:white;border-color:transparent}
.stab[data-s="todos"].active{background:#334155}
.stab[data-s="B2-03"].active{background:var(--b203)}
.stab[data-s="B1-01"].active{background:var(--b101)}
.stab[data-s="Injecao"].active{background:var(--inj)}
.page{display:none}.page.active{display:block}
.kpi-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:12px;margin-bottom:1.5rem}
.kpi{background:var(--white);border-radius:10px;padding:14px 16px;border:1px solid var(--border)}
.kpi-l{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;margin-bottom:.35rem}
.kpi-v{font-size:26px;font-weight:700}
.kpi-s{font-size:11px;color:var(--muted);margin-top:.2rem}
.date-row{display:flex;align-items:center;gap:10px;margin-bottom:1.25rem}
.date-row select{flex:1;padding:8px 12px;border:1px solid var(--border);border-radius:8px;font-size:13px;background:var(--white);color:var(--text)}
.sec-label{font-size:11px;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;margin-bottom:.75rem}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px;margin-bottom:1.5rem}
.card{background:var(--white);border:1px solid var(--border);border-radius:12px;padding:1.25rem;position:relative;overflow:hidden}
.card::before{content:"";position:absolute;top:0;left:0;right:0;height:4px;border-radius:12px 12px 0 0}
.sv::before{background:var(--green)}.at::before{background:var(--amber)}.no::before{background:var(--red)}.em::before{background:var(--border)}
.cname{font-size:11px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;margin-bottom:.2rem}
.cmeta{font-size:11px;color:var(--muted);margin-bottom:.75rem}
.cpct{font-size:44px;font-weight:700;line-height:1;margin-bottom:.2rem}
.sv .cpct{color:var(--green)}.at .cpct{color:var(--amber)}.no .cpct{color:var(--red)}.em .cpct{color:#CBD5E0}
.csub{font-size:12px;color:var(--muted);margin-bottom:.75rem}
.bar{height:5px;background:#EDF2F7;border-radius:3px;margin-bottom:1rem;overflow:hidden}
.bar-f{height:5px;border-radius:3px}
.sv .bar-f{background:var(--green)}.at .bar-f{background:var(--amber)}.no .bar-f{background:var(--red)}.em .bar-f{background:#CBD5E0}
.cstats{display:grid;grid-template-columns:repeat(3,1fr);border-top:1px solid var(--border);padding-top:.75rem}
.csv{font-size:18px;font-weight:700;text-align:center}
.csl{font-size:10px;color:var(--muted);text-align:center;margin-top:2px}
.pill{display:inline-flex;align-items:center;gap:4px;font-size:11px;font-weight:600;padding:3px 10px;border-radius:20px;margin-top:.6rem}
.sv .pill{background:var(--green-bg);color:var(--green)}.at .pill{background:var(--amber-bg);color:var(--amber)}.no .pill{background:var(--red-bg);color:var(--red)}.em .pill{background:#F7FAFC;color:var(--muted)}
.nc-row{display:flex;justify-content:space-between;font-size:11px;border-top:1px solid var(--border);padding-top:.5rem;margin-top:.5rem}
.nc-b{color:var(--red);font-weight:700}.nc-g{color:var(--green);font-weight:700}
.tw{background:var(--white);border:1px solid var(--border);border-radius:10px;overflow:hidden;margin-bottom:1.25rem}
table{width:100%;border-collapse:collapse;font-size:12px;table-layout:fixed}
th{background:#F7FAFC;padding:9px 12px;text-align:left;font-size:10px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;border-bottom:1px solid var(--border)}
td{padding:8px 12px;color:var(--text);border-bottom:1px solid var(--border);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
tr:last-child td{border-bottom:none}
tr:nth-child(even) td{background:#FAFAFA}
.tag{display:inline-block;padding:2px 8px;border-radius:4px;font-size:10px;font-weight:600}
.tok{background:#ECFDF5;color:#065F46}.tnc{background:#FEF2F2;color:#991B1B}.tts{background:#FFFBEB;color:#92400E}
.divider{border:none;border-top:1px solid var(--border);margin:1.25rem 0}
.upload-form{background:var(--white);border:1px solid var(--border);border-radius:12px;padding:1.5rem}
.upload-form h3{font-size:16px;font-weight:700;margin-bottom:1rem}
.form-group{margin-bottom:1rem}
.form-group label{display:block;font-size:12px;font-weight:600;color:var(--muted);margin-bottom:.35rem;text-transform:uppercase;letter-spacing:.04em}
.form-group input,.form-group select{width:100%;padding:9px 12px;border:1px solid var(--border);border-radius:8px;font-size:13px;font-family:inherit;background:var(--white);color:var(--text)}
.form-group input[type=password]{letter-spacing:.1em}
.submit-btn{width:100%;padding:10px;background:#05B15D;color:white;border:none;border-radius:8px;font-size:14px;font-weight:600;cursor:pointer;font-family:inherit;margin-top:.5rem}
.submit-btn:hover{background:#047a42}
.submit-btn:disabled{opacity:.6;cursor:not-allowed}
.msg{padding:10px 14px;border-radius:8px;font-size:13px;margin-top:.75rem;display:none}
.msg.ok{background:var(--green-bg);color:#065F46;display:block}
.msg.err{background:var(--red-bg);color:#991B1B;display:block}
.loading{text-align:center;padding:3rem;color:var(--muted);font-size:13px}
.empty{text-align:center;padding:3rem;color:var(--muted);font-size:13px}
.setor-section{margin-bottom:2rem}
.setor-header{display:flex;align-items:center;gap:10px;margin-bottom:1rem}
.setor-dot{width:12px;height:12px;border-radius:3px}
.setor-title{font-size:16px;font-weight:700}
.setor-sub{font-size:12px;color:var(--muted);margin-left:auto}
.del-btn{font-size:11px;color:var(--red);background:none;border:1px solid #FCA5A5;border-radius:4px;padding:3px 10px;cursor:pointer}
</style>
</head>
<body>
<div class="header">
  <div class="header-left">
    <h1>Controle de Inspeções</h1>
    <p>Zagonel · Qualidade Industrial</p>
  </div>
  <div class="header-right" id="last-update">Carregando...</div>
</div>

<div class="main">
  <div class="sector-tabs">
    <button class="stab active" data-s="todos" onclick="setSetor('todos',this)">Todos os setores</button>
    <button class="stab" data-s="B2-03" onclick="setSetor('B2-03',this)">Apoio B2-03</button>
    <button class="stab" data-s="B1-01" onclick="setSetor('B1-01',this)">Apoio B1-01</button>
    <button class="stab" data-s="Injecao" onclick="setSetor('Injecao',this)">Injeção</button>
    <button class="stab" data-s="importar" onclick="setSetor('importar',this)" style="margin-left:auto">⬆ Importar</button>
  </div>

  <div id="pg-todos" class="page active"><div id="todos-content"><div class="loading">Carregando dados...</div></div></div>
  <div id="pg-B2-03" class="page"><div id="B203-content"><div class="loading">Carregando...</div></div></div>
  <div id="pg-B1-01" class="page"><div id="B101-content"><div class="loading">Carregando...</div></div></div>
  <div id="pg-Injecao" class="page"><div id="Inj-content"><div class="loading">Carregando...</div></div></div>

  <div id="pg-importar" class="page">
    <div class="upload-form">
      <h3>Importar planilha diária</h3>
      <div class="form-group">
        <label>Setor</label>
        <select id="up-setor">
          <option value="B2-03">Apoio B2-03</option>
          <option value="B1-01">Apoio B1-01</option>
          <option value="Injecao">Injeção</option>
        </select>
      </div>
      <div class="form-group">
        <label>Arquivo .xlsx</label>
        <input type="file" id="up-file" accept=".xlsx">
      </div>
      <div class="form-group">
        <label>Senha de acesso</label>
        <input type="password" id="up-key" placeholder="••••••••">
      </div>
      <button class="submit-btn" id="up-btn" onclick="doUpload()">Importar dados</button>
      <div class="msg" id="up-msg"></div>
    </div>
    <div id="days-list" style="margin-top:1.5rem"></div>
  </div>
</div>

<script>
const SETORES_NOMES = {{ setores|safe }};
const SETORES_CORES = {{ cores|safe }};
let DB = {}, setor_atual = 'todos';

async function loadData(){
  try{
    const r = await fetch('/api/data');
    DB = await r.json();
    const n = Object.values(DB).reduce((a,s)=>a+Object.keys(s).length,0);
    document.getElementById('last-update').textContent = n + ' dias registrados';
    renderAll();
  }catch(e){
    document.getElementById('last-update').textContent = 'Erro ao carregar dados';
  }
}

function setSetor(s, btn){
  setor_atual = s;
  document.querySelectorAll('.stab').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
  document.getElementById('pg-'+s).classList.add('active');
  if(s === 'todos') renderTodos();
  else if(s !== 'importar') renderSetor(s);
  else renderDaysList();
}

function fmtDate(k){ const d=new Date(k+'T12:00:00'); return String(d.getDate()).padStart(2,'0')+'/'+String(d.getMonth()+1).padStart(2,'0')+'/'+d.getFullYear() }
function fmtTime(s){ if(!s)return'—'; const d=new Date(s); return String(d.getHours()).padStart(2,'0')+':'+String(d.getMinutes()).padStart(2,'0') }
function fmtDur(m){ if(m==null||isNaN(m))return'—'; const mi=Math.floor(m),s=Math.round((m-mi)*60); return mi+'min '+String(s).padStart(2,'0')+'s' }

function getClassif(pct){
  if(pct===0) return 'em';
  if(pct<85) return 'no';
  if(pct<=100) return 'at';
  return 'sv';
}

function pillLabel(cl){
  if(cl==='sv') return '▲ Superou';
  if(cl==='at') return '● Atingiu a meta';
  if(cl==='no') return '✕ Não atingiu';
  return '— Sem dados';
}

function buildCard(nome, dados){
  const tot = dados.total || 0;
  const meta = dados.meta || 0;
  const nc = dados.nc || 0;
  const pct = meta > 0 ? Math.round(tot/meta*100) : 0;
  const cl = tot===0 ? 'em' : getClassif(pct);
  return `<div class="card ${cl}">
    <div class="cname">${nome}</div>
    <div class="cmeta">Meta: ${meta} inspeções/dia</div>
    <div class="cpct">${tot===0?'—':pct+'%'}</div>
    <div class="csub">${tot===0?'Sem registros':tot+' realizadas · meta '+meta}</div>
    <div class="bar"><div class="bar-f" style="width:${tot===0?0:Math.min(pct,100)}%"></div></div>
    <div class="cstats">
      <div><div class="csv">${tot}</div><div class="csl">realizadas</div></div>
      <div><div class="csv">${tot-nc}</div><div class="csl">conformes</div></div>
      <div><div class="csv">${meta}</div><div class="csl">meta</div></div>
    </div>
    <span class="pill">${pillLabel(cl)}</span>
    <div class="nc-row"><span style="color:var(--muted)">NCs</span><span class="${nc>0?'nc-b':'nc-g'}">${nc} NC${nc!==1?'s':''}</span></div>
  </div>`;
}

function buildSetorPanel(setor_key, dia_key){
  const setor_data = (DB[setor_key] || {})[dia_key] || {};
  const nome_setor = SETORES_NOMES[setor_key] || setor_key;
  const cor = SETORES_CORES[setor_key] || '#334155';
  const colab = Object.entries(setor_data);
  if(!colab.length) return `<div class="empty">Sem dados para ${nome_setor} neste dia.</div>`;

  const tot = colab.reduce((a,[,d])=>a+d.total,0);
  const meta = colab.filter(([,d])=>d.total>0).reduce((a,[,d])=>a+d.meta,0);
  const nc = colab.reduce((a,[,d])=>a+d.nc,0);
  const pct = meta>0 ? Math.round(tot/meta*100) : 0;
  const nsv = colab.filter(([,d])=>d.total>0&&getClassif(Math.round(d.total/d.meta*100))==='sv').length;
  const nat = colab.filter(([,d])=>d.total>0&&getClassif(Math.round(d.total/d.meta*100))==='at').length;
  const nno = colab.filter(([,d])=>d.total>0&&getClassif(Math.round(d.total/d.meta*100))==='no').length;

  let h = `<div class="setor-section">
    <div class="setor-header">
      <div class="setor-dot" style="background:${cor}"></div>
      <div class="setor-title">${nome_setor}</div>
      <div class="setor-sub">${tot} insp · ${pct}% meta · ${nc} NC${nc!==1?'s':''}</div>
    </div>
    <div class="kpi-row">
      <div class="kpi"><div class="kpi-l">Inspeções</div><div class="kpi-v">${tot}</div><div class="kpi-s">meta: ${meta}</div></div>
      <div class="kpi"><div class="kpi-l">% da meta</div><div class="kpi-v" style="color:${pct>=100?'var(--green)':pct>=85?'var(--amber)':'var(--red)'}">${pct}%</div></div>
      <div class="kpi"><div class="kpi-l">Status</div><div class="kpi-v" style="font-size:14px;line-height:1.6">${nsv>0?`<span style="color:var(--green)">▲ ${nsv} superou</span><br>`:''}${nat>0?`<span style="color:var(--amber)">● ${nat} atingiu</span><br>`:''}${nno>0?`<span style="color:var(--red)">✕ ${nno} abaixo</span>`:''}
      </div></div>
    </div>
    <div class="cards">`;
  colab.forEach(([nome, dados])=>{ h += buildCard(nome, dados) });
  h += '</div></div>';
  return h;
}

function renderTodos(){
  const el = document.getElementById('todos-content');
  const todos_dias = [...new Set(Object.values(DB).flatMap(s=>Object.keys(s)))].sort((a,b)=>b.localeCompare(a));
  if(!todos_dias.length){ el.innerHTML='<div class="empty">Nenhum dado importado ainda. Vá em Importar para adicionar.</div>'; return }

  let h = '<div class="date-row"><div class="sec-label" style="margin:0;white-space:nowrap">Data</div><select id="todos-sel" onchange="renderTodosDay()"><'+'/select></div><div id="todos-day"></div>';
  el.innerHTML = h;
  const sel = document.getElementById('todos-sel');
  todos_dias.forEach((d,i)=>{ const opt=document.createElement('option'); opt.value=d; opt.textContent=fmtDate(d); if(i===0)opt.selected=true; sel.appendChild(opt) });
  renderTodosDay();
}

function renderTodosDay(){
  const dia = document.getElementById('todos-sel')?.value;
  if(!dia) return;
  let h = '';
  Object.keys(SETORES_NOMES).forEach(sk=>{ h += buildSetorPanel(sk, dia) });
  document.getElementById('todos-day').innerHTML = h;
}

function renderAll(){ renderTodos() }

function renderSetor(setor_key){
  const el = document.getElementById(setor_key.replace('-','')+''+'-content') ||
             document.getElementById({B203:'B203-content','B2-03':'B203-content','B1-01':'B101-content',Injecao:'Inj-content'}[setor_key] || setor_key+'-content');
  const id = setor_key==='B2-03'?'B203-content':setor_key==='B1-01'?'B101-content':'Inj-content';
  const container = document.getElementById(id);
  if(!container) return;

  const dias = Object.keys(DB[setor_key] || {}).sort((a,b)=>b.localeCompare(a));
  if(!dias.length){ container.innerHTML='<div class="empty">Nenhum dado importado para este setor.</div>'; return }

  let h = '<div class="date-row"><div class="sec-label" style="margin:0;white-space:nowrap">Data</div><select id="sel-'+setor_key+'" onchange="renderSetorDay(\''+setor_key+'\')">';
  dias.forEach((d,i)=>h+=`<option value="${d}"${i===0?' selected':''}>${fmtDate(d)}</option>`);
  h += '</select></div><div id="day-'+setor_key+'"></div>';
  container.innerHTML = h;
  renderSetorDay(setor_key);
}

function renderSetorDay(setor_key){
  const dia = document.getElementById('sel-'+setor_key)?.value;
  if(!dia) return;
  const id = setor_key==='B2-03'?'B203-content':setor_key==='B1-01'?'B101-content':'Inj-content';
  const setor_data = (DB[setor_key]||{})[dia]||{};
  const colab = Object.entries(setor_data);
  let h = buildSetorPanel(setor_key, dia);

  // Detalhes por colaborador
  colab.forEach(([nome, dados])=>{
    if(!dados.inspecoes||!dados.inspecoes.length) return;
    h += `<div class="divider"></div><div class="sec-label">${nome} — ${dados.total} inspeções</div>`;
    h += '<div class="tw"><table><thead><tr><th style="width:24px">#</th><th>Atividade</th><th style="width:58px">Início</th><th style="width:58px">Fim</th><th style="width:80px">Duração</th><th style="width:80px">Status</th></tr></thead><tbody>';
    dados.inspecoes.forEach((ins,i)=>{
      const nc=ins.cf==='Não',te=!ins.cf;
      const tag=nc?'<span class="tag tnc">NC</span>':te?'<span class="tag tts">Teste</span>':'<span class="tag tok">Conforme</span>';
      h+=`<tr><td>${i+1}</td><td>${ins.at||'—'}</td><td>${fmtTime(ins.ini)}</td><td>${fmtTime(ins.fim)}</td><td>${fmtDur(ins.dur)}</td><td>${tag}</td></tr>`;
    });
    h += '</tbody></table></div>';
  });
  document.getElementById('day-'+setor_key).innerHTML = h;
}

async function doUpload(){
  const setor = document.getElementById('up-setor').value;
  const file = document.getElementById('up-file').files[0];
  const key = document.getElementById('up-key').value;
  const btn = document.getElementById('up-btn');
  const msg = document.getElementById('up-msg');
  msg.className='msg'; msg.style.display='none';
  if(!file){ msg.textContent='Selecione um arquivo .xlsx'; msg.className='msg err'; return }
  if(!key){ msg.textContent='Digite a senha de acesso'; msg.className='msg err'; return }
  btn.disabled=true; btn.textContent='Importando...';
  const fd = new FormData();
  fd.append('setor', setor); fd.append('file', file); fd.append('key', key);
  try{
    const r = await fetch('/api/upload', {method:'POST', body:fd});
    const d = await r.json();
    if(d.ok){
      msg.textContent = `✓ Dia ${d.data} importado — ${d.setor} — ${d.colaboradores.join(', ')}`;
      msg.className='msg ok';
      document.getElementById('up-file').value='';
      await loadData();
      renderDaysList();
    } else {
      msg.textContent = d.error || 'Erro ao importar';
      msg.className='msg err';
    }
  }catch(e){
    msg.textContent = 'Erro de conexão: '+e.message;
    msg.className='msg err';
  }
  btn.disabled=false; btn.textContent='Importar dados';
}

function renderDaysList(){
  const el = document.getElementById('days-list');
  const itens = [];
  Object.entries(DB).forEach(([sk, dias])=>{
    Object.entries(dias).forEach(([dk, colab])=>{
      const tot = Object.values(colab).reduce((a,c)=>a+c.total,0);
      const nc = Object.values(colab).reduce((a,c)=>a+c.nc,0);
      itens.push({sk, dk, tot, nc, nomes: Object.keys(colab)});
    });
  });
  itens.sort((a,b)=>b.dk.localeCompare(a.dk));
  if(!itens.length){ el.innerHTML=''; return }
  let h = '<div class="sec-label">Dias importados</div><div class="tw"><table><thead><tr><th>Setor</th><th>Data</th><th>Colaboradores</th><th>Total</th><th>NCs</th><th></th></tr></thead><tbody>';
  itens.forEach(i=>{
    h+=`<tr><td style="font-weight:600;color:${SETORES_CORES[i.sk]}">${SETORES_NOMES[i.sk]}</td><td style="font-weight:600">${fmtDate(i.dk)}</td><td style="font-size:11px;color:var(--muted)">${i.nomes.join(', ')}</td><td>${i.tot}</td><td>${i.nc>0?`<span class="tag tnc">${i.nc}</span>`:'<span class="tag tok">0</span>'}</td><td><button class="del-btn" onclick="delDay('${i.sk}','${i.dk}')">Remover</button></td></tr>`;
  });
  h += '</tbody></table></div>';
  el.innerHTML = h;
}

async function delDay(sk, dk){
  if(!confirm(`Remover ${SETORES_NOMES[sk]} - ${fmtDate(dk)}?`)) return;
  const key = prompt('Senha de acesso:');
  if(!key) return;
  await fetch('/api/delete', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({setor:sk, data:dk, key})});
  await loadData();
  renderDaysList();
}

loadData();
</script>
</body>
</html>'''

if __name__ == '__main__':
    app.run(debug=True)
