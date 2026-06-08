import os, json, base64, requests
from flask import Flask, request, jsonify, Response
from datetime import datetime
import pandas as pd
from io import BytesIO

app = Flask(__name__)

DATA_FILE    = os.environ.get('DATA_FILE', 'data.json')
UPLOAD_KEY   = os.environ.get('UPLOAD_KEY', 'zagonel2026')
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
GITHUB_REPO  = os.environ.get('GITHUB_REPO', '')

SETORES = {
    'B2-03': {
        'nome': 'Apoio B2-03', 'cor': '#2563EB',
        'colaboradores': {'Juliana': 30, 'Sirlei': 30, 'Danmari': 29},
        'campos_executor': ['Executor', 'Executor do teste'],
    },
    'B1-01': {
        'nome': 'Apoio B1-01', 'cor': '#059669',
        'colaboradores': {'Luana': 28, 'Bruna': 27},
        'campos_executor': ['Responsável pela conferência', 'Executor', 'Executor do teste'],
    },
    'Injecao': {
        'nome': 'Injeção', 'cor': '#7C3AED',
        'colaboradores': {},
        'campos_executor': ['Executor', 'Executor do teste'],
        'meta_padrao': 15,
        'metas_fixas': {'jocemar': 20, 'kaue': 18},
    },
}

def load_data():
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE) as f:
                return json.load(f)
    except: pass
    if GITHUB_TOKEN and GITHUB_REPO:
        try:
            r = requests.get(
                f'https://api.github.com/repos/{GITHUB_REPO}/contents/data.json',
                headers={'Authorization': f'token {GITHUB_TOKEN}'}, timeout=5)
            if r.status_code == 200:
                return json.loads(base64.b64decode(r.json()['content']).decode())
        except: pass
    return {'B2-03': {}, 'B1-01': {}, 'Injecao': {}}

def save_data(data):
    try:
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f, ensure_ascii=False, default=str)
    except: pass
    if GITHUB_TOKEN and GITHUB_REPO:
        try:
            content = base64.b64encode(json.dumps(data, ensure_ascii=False, default=str).encode()).decode()
            r = requests.get(
                f'https://api.github.com/repos/{GITHUB_REPO}/contents/data.json',
                headers={'Authorization': f'token {GITHUB_TOKEN}'}, timeout=5)
            sha = r.json().get('sha', '') if r.status_code == 200 else ''
            payload = {'message': f'update {datetime.now().strftime("%Y-%m-%d %H:%M")}', 'content': content}
            if sha: payload['sha'] = sha
            requests.put(
                f'https://api.github.com/repos/{GITHUB_REPO}/contents/data.json',
                headers={'Authorization': f'token {GITHUB_TOKEN}'},
                json=payload, timeout=10)
        except: pass

def norm_name(n, setor_key):
    if not n: return None
    s = str(n).strip()
    for nome in SETORES[setor_key].get('colaboradores', {}):
        if nome.lower() in s.lower():
            return nome
    if setor_key == 'Injecao' and len(s) > 3:
        return s.title()
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
    try:
        df = pd.read_excel(BytesIO(file_bytes))
    except Exception as e:
        return None, None, str(e)
    campos_exec = SETORES[setor_key]['campos_executor']
    by_code = {}
    for _, row in df.iterrows():
        cod = row.get('Código da avaliação')
        if cod is None or (isinstance(cod, float) and pd.isna(cod)): continue
        cod = str(cod)
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
        ini = row.get('Data inicial')
        fim = row.get('Data final')
        if not by_code[cod]['ini'] and ini is not None and str(ini) not in ('', 'nan'):
            by_code[cod]['ini'] = ini
        if fim is not None and str(fim) not in ('', 'nan'):
            by_code[cod]['fim'] = fim
    inspecoes = []
    for o in by_code.values():
        if not o['ex'] or not o['at']: continue
        try:
            ini = pd.to_datetime(o['ini'], dayfirst=True) if o['ini'] is not None else None
            fim = pd.to_datetime(o['fim'], dayfirst=True) if o['fim'] is not None else None
            dur = round((fim - ini).total_seconds() / 60, 2) if ini and fim and fim > ini else None
            inspecoes.append({
                'at': o['at'], 'ex': o['ex'], 'cf': o['cf'],
                'ini': ini.strftime('%Y-%m-%dT%H:%M:%S') if ini else None,
                'fim': fim.strftime('%Y-%m-%dT%H:%M:%S') if fim else None,
                'dur': dur
            })
        except: continue
    if not inspecoes: return None, None, 'Nenhuma inspeção encontrada'
    ref = next((i['ini'] for i in inspecoes if i['ini']), None)
    if not ref: return None, None, 'Datas não encontradas'
    data_key = ref[:10]
    colaboradores = {}
    for ins in inspecoes:
        p = ins['ex']
        if p not in colaboradores:
            colaboradores[p] = {'meta': get_meta(p, setor_key), 'total': 0, 'nc': 0, 'teste': 0, 'inspecoes': []}
        colaboradores[p]['total'] += 1
        if ins['cf'] == 'Não': colaboradores[p]['nc'] += 1
        if not ins['cf']: colaboradores[p]['teste'] += 1
        colaboradores[p]['inspecoes'].append({
            'at': ins['at'], 'cf': ins['cf'],
            'ini': ins['ini'], 'fim': ins['fim'], 'dur': ins['dur']
        })
    return data_key, colaboradores, None

@app.route('/api/config')
def api_config():
    return jsonify({
        'setores': {k: {'nome': v['nome'], 'cor': v['cor']} for k, v in SETORES.items()}
    })

@app.route('/api/data')
def api_data():
    return jsonify(load_data())

@app.route('/api/upload', methods=['POST'])
def api_upload():
    if request.form.get('key') != UPLOAD_KEY:
        return jsonify({'error': 'Senha incorreta'}), 401
    setor = request.form.get('setor')
    if setor not in SETORES:
        return jsonify({'error': 'Setor inválido'}), 400
    file = request.files.get('file')
    if not file:
        return jsonify({'error': 'Arquivo não enviado'}), 400
    data_key, colaboradores, err = parse_xlsx(file.read(), setor)
    if err:
        return jsonify({'error': err}), 400
    db = load_data()
    if setor not in db: db[setor] = {}
    db[setor][data_key] = colaboradores
    save_data(db)
    d = datetime.strptime(data_key, '%Y-%m-%d')
    return jsonify({'ok': True, 'data': d.strftime('%d/%m/%Y'),
                    'setor': SETORES[setor]['nome'],
                    'colaboradores': list(colaboradores.keys())})

@app.route('/api/delete', methods=['POST'])
def api_delete():
    data = request.get_json() or {}
    if data.get('key') != UPLOAD_KEY:
        return jsonify({'error': 'Senha incorreta'}), 401
    setor, dk = data.get('setor'), data.get('data')
    db = load_data()
    if setor in db and dk in db[setor]:
        del db[setor][dk]
        save_data(db)
    return jsonify({'ok': True})

@app.route('/')
def index():
    return Response(HTML, mimetype='text/html')

HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Controle de Inspeções — Zagonel</title>
<style>
:root{--bg:#F0F4F8;--white:#fff;--border:#E2E8F0;--text:#1A202C;--muted:#718096;
  --green:#059669;--amber:#D97706;--red:#DC2626;
  --green-bg:#ECFDF5;--amber-bg:#FFFBEB;--red-bg:#FEF2F2}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:var(--bg);color:var(--text);min-height:100vh}
.topbar{background:#05B15D;color:#fff;padding:.85rem 1.5rem;display:flex;justify-content:space-between;align-items:center}
.topbar h1{font-size:18px;font-weight:700}
.topbar p{font-size:11px;opacity:.85;margin-top:2px}
.main{max-width:1200px;margin:0 auto;padding:1.5rem}
.tabs{display:flex;gap:8px;margin-bottom:1.5rem;flex-wrap:wrap;align-items:center}
.tab{padding:8px 18px;border-radius:8px;font-size:13px;font-weight:500;cursor:pointer;border:1.5px solid var(--border);background:var(--white);color:var(--muted);transition:.15s}
.tab:hover{border-color:#94A3B8;color:var(--text)}
.tab.on{color:#fff;border-color:transparent}
.tab[data-s="todos"].on{background:#334155}
.tab[data-s="imp"].on{background:#05B15D}
.tab-imp{margin-left:auto}
.pg{display:none}.pg.on{display:block}
.kgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:12px;margin-bottom:1.5rem}
.kcard{background:var(--white);border:1px solid var(--border);border-radius:10px;padding:14px 16px}
.kl{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;margin-bottom:.35rem}
.kv{font-size:26px;font-weight:700}
.ks{font-size:11px;color:var(--muted);margin-top:.2rem}
.cgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px;margin-bottom:1.5rem}
.card{background:var(--white);border:1px solid var(--border);border-radius:12px;padding:1.25rem;position:relative;overflow:hidden}
.card::before{content:"";position:absolute;top:0;left:0;right:0;height:4px;border-radius:12px 12px 0 0}
.sv::before{background:var(--green)}.at::before{background:var(--amber)}.no::before{background:var(--red)}.em::before{background:var(--border)}
.cn{font-size:11px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;margin-bottom:.2rem}
.cm{font-size:11px;color:var(--muted);margin-bottom:.75rem}
.cpct{font-size:44px;font-weight:700;line-height:1;margin-bottom:.2rem}
.sv .cpct{color:var(--green)}.at .cpct{color:var(--amber)}.no .cpct{color:var(--red)}.em .cpct{color:#CBD5E0}
.csub{font-size:12px;color:var(--muted);margin-bottom:.75rem}
.bar{height:5px;background:#EDF2F7;border-radius:3px;margin-bottom:1rem;overflow:hidden}
.bar-f{height:5px;border-radius:3px}
.sv .bar-f{background:var(--green)}.at .bar-f{background:var(--amber)}.no .bar-f{background:var(--red)}.em .bar-f{background:#CBD5E0}
.cst{display:grid;grid-template-columns:repeat(3,1fr);border-top:1px solid var(--border);padding-top:.75rem}
.csv2{font-size:18px;font-weight:700;text-align:center}
.csl{font-size:10px;color:var(--muted);text-align:center;margin-top:2px}
.pill{display:inline-flex;align-items:center;gap:4px;font-size:11px;font-weight:600;padding:3px 10px;border-radius:20px;margin-top:.6rem}
.sv .pill{background:var(--green-bg);color:var(--green)}.at .pill{background:var(--amber-bg);color:var(--amber)}.no .pill{background:var(--red-bg);color:var(--red)}.em .pill{background:#F7FAFC;color:var(--muted)}
.ncr{display:flex;justify-content:space-between;font-size:11px;border-top:1px solid var(--border);padding-top:.5rem;margin-top:.5rem}
.ncb{color:var(--red);font-weight:700}.ncg{color:var(--green);font-weight:700}
.dsel{display:flex;align-items:center;gap:10px;margin-bottom:1.25rem}
.dsel select{flex:1;padding:8px 12px;border:1px solid var(--border);border-radius:8px;font-size:13px;background:var(--white);color:var(--text);font-family:inherit}
.sl{font-size:11px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;margin-bottom:.75rem}
.tw{background:var(--white);border:1px solid var(--border);border-radius:10px;overflow:hidden;margin-bottom:1.25rem}
table{width:100%;border-collapse:collapse;font-size:12px;table-layout:fixed}
th{background:#F7FAFC;padding:9px 12px;text-align:left;font-size:10px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;border-bottom:1px solid var(--border)}
td{padding:8px 12px;border-bottom:1px solid var(--border);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
tr:last-child td{border-bottom:none}
tr:nth-child(even) td{background:#FAFAFA}
.tag{display:inline-block;padding:2px 8px;border-radius:4px;font-size:10px;font-weight:600}
.tok{background:#ECFDF5;color:#065F46}.tnc{background:#FEF2F2;color:#991B1B}.tts{background:#FFFBEB;color:#92400E}
.divider{border:none;border-top:1px solid var(--border);margin:1.25rem 0}
.sec-block{margin-bottom:2rem}
.sec-hdr{display:flex;align-items:center;gap:8px;margin-bottom:1rem}
.sec-dot{width:12px;height:12px;border-radius:3px}
.sec-title{font-size:16px;font-weight:700}
.sec-sub{font-size:12px;color:var(--muted);margin-left:auto}
.upform{background:var(--white);border:1px solid var(--border);border-radius:12px;padding:1.5rem;max-width:520px}
.upform h3{font-size:16px;font-weight:700;margin-bottom:1rem}
.fg{margin-bottom:1rem}
.fg label{display:block;font-size:11px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.04em;margin-bottom:.35rem}
.fg input,.fg select{width:100%;padding:9px 12px;border:1px solid var(--border);border-radius:8px;font-size:13px;font-family:inherit;background:var(--white);color:var(--text)}
.upbtn{width:100%;padding:11px;background:#05B15D;color:#fff;border:none;border-radius:8px;font-size:14px;font-weight:700;cursor:pointer;font-family:inherit}
.upbtn:hover{background:#047a42}.upbtn:disabled{opacity:.6;cursor:not-allowed}
.msg{padding:10px 14px;border-radius:8px;font-size:13px;margin-top:.75rem}
.msg.ok{background:var(--green-bg);color:#065F46}
.msg.err{background:var(--red-bg);color:#991B1B}
.del-btn{font-size:11px;color:var(--red);background:none;border:1px solid #FCA5A5;border-radius:4px;padding:3px 10px;cursor:pointer}
.empty{text-align:center;padding:3rem;color:var(--muted);font-size:13px}
.loading{text-align:center;padding:3rem;color:var(--muted);font-size:13px}
</style>
</head>
<body>
<div class="topbar">
  <div><h1>Controle de Inspeções</h1><p>Zagonel · Qualidade Industrial</p></div>
  <div id="topinfo" style="font-size:12px;opacity:.8">Carregando...</div>
</div>
<div class="main">
  <div class="tabs" id="tabs">
    <button class="tab on" data-s="todos" onclick="goTab('todos',this)">Todos os setores</button>
    <button class="tab tab-imp" data-s="imp" onclick="goTab('imp',this)">&#8679; Importar</button>
  </div>
  <div id="pg-todos" class="pg on"><div id="c-todos"><div class="loading">Carregando dados...</div></div></div>
  <div id="pg-imp" class="pg">
    <div class="upform">
      <h3>Importar planilha diária</h3>
      <div class="fg"><label>Setor</label>
        <select id="up-s"></select>
      </div>
      <div class="fg"><label>Arquivo .xlsx</label><input type="file" id="up-f" accept=".xlsx"></div>
      <div class="fg"><label>Senha</label><input type="password" id="up-k" placeholder="••••••••"></div>
      <button class="upbtn" id="up-btn" onclick="doUpload()">Importar dados</button>
      <div class="msg" id="up-msg" style="display:none"></div>
    </div>
    <div id="days-list" style="margin-top:1.5rem"></div>
  </div>
</div>

<script>
var DB = {}, CFG = {}, tab = 'todos';

async function init() {
  try {
    var rc = await fetch('/api/config');
    CFG = await rc.json();
    var rd = await fetch('/api/data');
    DB = await rd.json();

    // Criar tabs dos setores dinamicamente
    var tabsEl = document.getElementById('tabs');
    var impTab = tabsEl.querySelector('.tab-imp');
    Object.keys(CFG.setores).forEach(function(sk) {
      var b = document.createElement('button');
      b.className = 'tab';
      b.setAttribute('data-s', sk);
      b.textContent = CFG.setores[sk].nome;
      b.style.setProperty('--sc', CFG.setores[sk].cor);
      b.onclick = function() { goTab(sk, b); };
      tabsEl.insertBefore(b, impTab);

      // Criar página do setor
      var pg = document.createElement('div');
      pg.id = 'pg-' + sk;
      pg.className = 'pg';
      var inner = document.createElement('div');
      inner.id = 'c-' + sk;
      pg.appendChild(inner);
      document.querySelector('.main').appendChild(pg);
    });

    // CSS dinâmico para tabs dos setores
    var style = document.createElement('style');
    Object.keys(CFG.setores).forEach(function(sk) {
      style.textContent += '.tab[data-s="' + sk + '"].on { background: ' + CFG.setores[sk].cor + '; }';
    });
    document.head.appendChild(style);

    // Preencher select de setores
    var sel = document.getElementById('up-s');
    Object.keys(CFG.setores).forEach(function(sk) {
      var opt = document.createElement('option');
      opt.value = sk;
      opt.textContent = CFG.setores[sk].nome;
      sel.appendChild(opt);
    });

    var n = Object.values(DB).reduce(function(a, s) { return a + Object.keys(s).length; }, 0);
    document.getElementById('topinfo').textContent = n + ' dias registrados';
    rTodos();
  } catch(e) {
    document.getElementById('topinfo').textContent = 'Erro ao carregar';
    document.getElementById('c-todos').innerHTML = '<div class="empty">Erro ao carregar dados. Recarregue a página.</div>';
  }
}

function goTab(s, b) {
  tab = s;
  document.querySelectorAll('.tab').forEach(function(x) { x.classList.remove('on'); });
  b.classList.add('on');
  document.querySelectorAll('.pg').forEach(function(x) { x.classList.remove('on'); });
  document.getElementById('pg-' + s).classList.add('on');
  if (s === 'todos') rTodos();
  else if (s !== 'imp') rSetor(s);
  else rDaysList();
}

function fD(k) {
  var d = new Date(k + 'T12:00:00');
  return String(d.getDate()).padStart(2,'0') + '/' + String(d.getMonth()+1).padStart(2,'0') + '/' + d.getFullYear();
}
function fT(s) {
  if (!s) return '—';
  var d = new Date(s);
  return String(d.getHours()).padStart(2,'0') + ':' + String(d.getMinutes()).padStart(2,'0');
}
function fDur(m) {
  if (m == null || isNaN(m)) return '—';
  var mi = Math.floor(m), s = Math.round((m - mi) * 60);
  return mi + 'min ' + String(s).padStart(2,'0') + 's';
}
function cl(pct, tot) {
  if (!tot) return 'em';
  if (pct < 85) return 'no';
  if (pct <= 100) return 'at';
  return 'sv';
}
function pillTxt(c) {
  return c==='sv' ? '&#9650; Superou' : c==='at' ? '&#9679; Atingiu a meta' : c==='no' ? '&#10005; Não atingiu' : '— Sem dados';
}

function buildCard(nome, d) {
  var tot = d.total || 0, meta = d.meta || 0, nc = d.nc || 0;
  var pct = meta > 0 ? Math.round(tot / meta * 100) : 0;
  var c = cl(pct, tot);
  return '<div class="card ' + c + '">' +
    '<div class="cn">' + nome + '</div>' +
    '<div class="cm">Meta: ' + meta + ' inspeções/dia</div>' +
    '<div class="cpct">' + (!tot ? '—' : pct + '%') + '</div>' +
    '<div class="csub">' + (!tot ? 'Sem registros' : tot + ' realizadas · meta ' + meta) + '</div>' +
    '<div class="bar"><div class="bar-f" style="width:' + (!tot ? 0 : Math.min(pct,100)) + '%"></div></div>' +
    '<div class="cst">' +
      '<div><div class="csv2">' + tot + '</div><div class="csl">realizadas</div></div>' +
      '<div><div class="csv2">' + (tot-nc) + '</div><div class="csl">conformes</div></div>' +
      '<div><div class="csv2">' + meta + '</div><div class="csl">meta</div></div>' +
    '</div>' +
    '<span class="pill">' + pillTxt(c) + '</span>' +
    '<div class="ncr"><span style="color:var(--muted)">NCs evidenciadas</span>' +
      '<span class="' + (nc>0?'ncb':'ncg') + '">' + nc + ' NC' + (nc!==1?'s':'') + '</span></div>' +
    '</div>';
}

function buildSetor(sk, dk) {
  var sd = (DB[sk] || {})[dk] || {};
  var col = Object.entries(sd);
  var nome_setor = CFG.setores[sk] ? CFG.setores[sk].nome : sk;
  var cor = CFG.setores[sk] ? CFG.setores[sk].cor : '#334155';
  if (!col.length) return '<div class="empty">Sem dados para ' + nome_setor + ' neste dia.</div>';
  var tot = col.reduce(function(a,x){return a+x[1].total;},0);
  var meta = col.filter(function(x){return x[1].total>0;}).reduce(function(a,x){return a+x[1].meta;},0);
  var nc = col.reduce(function(a,x){return a+x[1].nc;},0);
  var pct = meta > 0 ? Math.round(tot/meta*100) : 0;
  var nsv=0,nat=0,nno=0;
  col.forEach(function(x) {
    if (!x[1].total) return;
    var p = Math.round(x[1].total/x[1].meta*100);
    var c = cl(p, x[1].total);
    if (c==='sv') nsv++; else if (c==='at') nat++; else nno++;
  });
  var h = '<div class="sec-block">' +
    '<div class="sec-hdr">' +
      '<div class="sec-dot" style="background:' + cor + '"></div>' +
      '<div class="sec-title">' + nome_setor + '</div>' +
      '<div class="sec-sub">' + tot + ' insp · ' + pct + '% meta · ' + nc + ' NC' + (nc!==1?'s':'') + '</div>' +
    '</div>' +
    '<div class="kgrid">' +
      '<div class="kcard"><div class="kl">Inspeções</div><div class="kv">' + tot + '</div><div class="ks">meta: ' + meta + '</div></div>' +
      '<div class="kcard"><div class="kl">% da meta</div><div class="kv" style="color:' + (pct>=100?'var(--green)':pct>=85?'var(--amber)':'var(--red)') + '">' + pct + '%</div></div>' +
      '<div class="kcard"><div class="kl">Status</div><div class="kv" style="font-size:13px;line-height:1.8">' +
        (nsv>0?'<span style="color:var(--green)">&#9650; '+nsv+' superou</span><br>':'') +
        (nat>0?'<span style="color:var(--amber)">&#9679; '+nat+' atingiu</span><br>':'') +
        (nno>0?'<span style="color:var(--red)">&#10005; '+nno+' abaixo</span>':'') +
      '</div></div>' +
    '</div>' +
    '<div class="cgrid">';
  col.forEach(function(x) { h += buildCard(x[0], x[1]); });
  h += '</div></div>';
  return h;
}

function rTodos() {
  var el = document.getElementById('c-todos');
  var dias = [];
  Object.values(DB).forEach(function(s) { Object.keys(s).forEach(function(d) { if (dias.indexOf(d)<0) dias.push(d); }); });
  dias.sort(function(a,b){return b.localeCompare(a);});
  if (!dias.length) { el.innerHTML = '<div class="empty">Nenhum dado importado. Vá em Importar para começar.</div>'; return; }
  var h = '<div class="dsel"><div class="sl" style="margin:0;white-space:nowrap">Data</div><select id="sel-todos" onchange="rTodosDay()">';
  dias.forEach(function(d,i) { h += '<option value="'+d+'"'+(i===0?' selected':'')+'>'+fD(d)+'</option>'; });
  h += '</select></div><div id="body-todos"></div>';
  el.innerHTML = h;
  rTodosDay();
}

function rTodosDay() {
  var dk = document.getElementById('sel-todos') ? document.getElementById('sel-todos').value : null;
  if (!dk) return;
  var h = '';
  Object.keys(CFG.setores).forEach(function(sk) { h += buildSetor(sk, dk); });
  document.getElementById('body-todos').innerHTML = h;
}

function rSetor(sk) {
  var el = document.getElementById('c-' + sk);
  if (!el) return;
  var dias = Object.keys(DB[sk] || {}).sort(function(a,b){return b.localeCompare(a);});
  if (!dias.length) { el.innerHTML = '<div class="empty">Nenhum dado para este setor. Importe uma planilha.</div>'; return; }
  var h = '<div class="dsel"><div class="sl" style="margin:0;white-space:nowrap">Data</div><select id="sel-'+sk+'" onchange="rSetorDay(\''+sk+'\')">';
  dias.forEach(function(d,i) { h += '<option value="'+d+'"'+(i===0?' selected':'')+'>'+fD(d)+'</option>'; });
  h += '</select></div><div id="body-'+sk+'"></div>';
  el.innerHTML = h;
  rSetorDay(sk);
}

function rSetorDay(sk) {
  var dk = document.getElementById('sel-'+sk) ? document.getElementById('sel-'+sk).value : null;
  if (!dk) return;
  var sd = (DB[sk] || {})[dk] || {};
  var h = buildSetor(sk, dk);
  Object.entries(sd).forEach(function(entry) {
    var nome = entry[0], d = entry[1];
    if (!d.inspecoes || !d.inspecoes.length) return;
    h += '<div class="divider"></div><div class="sl">' + nome + ' — ' + d.total + ' inspeções</div>';
    h += '<div class="tw"><table><thead><tr><th style="width:24px">#</th><th>Atividade</th><th style="width:58px">Início</th><th style="width:58px">Fim</th><th style="width:80px">Duração</th><th style="width:80px">Status</th></tr></thead><tbody>';
    d.inspecoes.forEach(function(ins, i) {
      var nc = ins.cf==='Não', te = !ins.cf;
      var tag = nc ? '<span class="tag tnc">NC</span>' : te ? '<span class="tag tts">Teste</span>' : '<span class="tag tok">Conforme</span>';
      h += '<tr><td>'+(i+1)+'</td><td>'+(ins.at||'—')+'</td><td>'+fT(ins.ini)+'</td><td>'+fT(ins.fim)+'</td><td>'+fDur(ins.dur)+'</td><td>'+tag+'</td></tr>';
    });
    h += '</tbody></table></div>';
  });
  document.getElementById('body-'+sk).innerHTML = h;
}

function rDaysList() {
  var el = document.getElementById('days-list');
  var itens = [];
  Object.entries(DB).forEach(function(se) {
    var sk = se[0];
    Object.entries(se[1]).forEach(function(de) {
      var dk = de[0], col = de[1];
      itens.push({sk:sk, dk:dk,
        tot: Object.values(col).reduce(function(a,c){return a+c.total;},0),
        nc:  Object.values(col).reduce(function(a,c){return a+c.nc;},0),
        nomes: Object.keys(col)
      });
    });
  });
  itens.sort(function(a,b){return b.dk.localeCompare(a.dk);});
  if (!itens.length) { el.innerHTML = ''; return; }
  var h = '<div class="sl">Dias importados</div><div class="tw"><table><thead><tr><th>Setor</th><th>Data</th><th>Colaboradores</th><th>Total</th><th>NCs</th><th></th></tr></thead><tbody>';
  itens.forEach(function(i) {
    var cor = CFG.setores[i.sk] ? CFG.setores[i.sk].cor : '#334155';
    var nome = CFG.setores[i.sk] ? CFG.setores[i.sk].nome : i.sk;
    h += '<tr><td style="font-weight:700;color:'+cor+'">'+nome+'</td><td style="font-weight:600">'+fD(i.dk)+'</td>' +
      '<td style="font-size:11px;color:var(--muted)">'+i.nomes.join(', ')+'</td><td>'+i.tot+'</td>' +
      '<td>'+(i.nc>0?'<span class="tag tnc">'+i.nc+'</span>':'<span class="tag tok">0</span>')+'</td>' +
      '<td><button class="del-btn" onclick="delDay(\''+i.sk+'\',\''+i.dk+'\')">Remover</button></td></tr>';
  });
  h += '</tbody></table></div>';
  el.innerHTML = h;
}

async function doUpload() {
  var setor = document.getElementById('up-s').value;
  var file = document.getElementById('up-f').files[0];
  var key = document.getElementById('up-k').value;
  var btn = document.getElementById('up-btn');
  var msg = document.getElementById('up-msg');
  msg.style.display = 'none';
  if (!file) { msg.textContent='Selecione um arquivo .xlsx'; msg.className='msg err'; msg.style.display='block'; return; }
  if (!key)  { msg.textContent='Digite a senha'; msg.className='msg err'; msg.style.display='block'; return; }
  btn.disabled = true; btn.textContent = 'Importando...';
  var fd = new FormData();
  fd.append('setor', setor); fd.append('file', file); fd.append('key', key);
  try {
    var r = await fetch('/api/upload', {method:'POST', body:fd});
    var d = await r.json();
    if (d.ok) {
      msg.textContent = '✓ Dia ' + d.data + ' importado — ' + d.setor + ' — ' + d.colaboradores.join(', ');
      msg.className = 'msg ok'; msg.style.display = 'block';
      document.getElementById('up-f').value = '';
      await init(); rDaysList();
    } else {
      msg.textContent = d.error || 'Erro ao importar';
      msg.className = 'msg err'; msg.style.display = 'block';
    }
  } catch(e) {
    msg.textContent = 'Erro: ' + e.message;
    msg.className = 'msg err'; msg.style.display = 'block';
  }
  btn.disabled = false; btn.textContent = 'Importar dados';
}

async function delDay(sk, dk) {
  if (!confirm('Remover ' + (CFG.setores[sk]?CFG.setores[sk].nome:sk) + ' - ' + fD(dk) + '?')) return;
  var key = prompt('Senha:');
  if (!key) return;
  await fetch('/api/delete', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({setor:sk,data:dk,key:key})});
  await init(); rDaysList();
}

init();
</script>
</body>
</html>"""

if __name__ == '__main__':
    app.run(debug=True)
