import os, json, base64, requests
from flask import Flask, request, jsonify, Response, session, redirect
from datetime import datetime
import pandas as pd
from io import BytesIO

app = Flask(__name__)

DATA_FILE    = 'data.json'
UPLOAD_KEY   = os.environ.get('UPLOAD_KEY', 'zagonel2026')
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
CF_API_KEY   = os.environ.get('CHECKLISTFACIL_API_KEY', '')
CF_API_URL         = 'https://integration.checklistfacil.com.br'
CF_API_ANALYTICS   = 'https://api-analytics.checklistfacil.com.br'
GITHUB_REPO  = os.environ.get('GITHUB_REPO', '')

app.secret_key = os.environ.get('SECRET_KEY', 'zagonel-secret-2026')

# Usuários do sistema — senhas configuráveis via variáveis de ambiente no Render
USUARIOS = {
    # Admin — acesso total a todos os setores
    'bruno':    {'senha': os.environ.get('PASS_BRUNO',    'Bruno@2026'),    'nome': 'Bruno',    'setores': ['B2-03','B1-01','Injecao']},
    # Encarregado — vê todos os setores (somente visualização)
    'luciano':  {'senha': os.environ.get('PASS_LUCIANO',  'Luciano@2026'),  'nome': 'Luciano',  'setores': ['B2-03','B1-01','Injecao']},
    # Apoio B2-03
    'maria':    {'senha': os.environ.get('PASS_MARIA',    'Maria@2026'),    'nome': 'Maria',    'setores': ['B2-03']},
    'juliana':  {'senha': os.environ.get('PASS_JULIANA',  'Juliana@2026'),  'nome': 'Juliana',  'setores': ['B2-03']},
    'sirlei':   {'senha': os.environ.get('PASS_SIRLEI',   'Sirlei@2026'),   'nome': 'Sirlei',   'setores': ['B2-03']},
    'danmari':  {'senha': os.environ.get('PASS_DANMARI',  'Danmari@2026'),  'nome': 'Danmari',  'setores': ['B2-03']},
    # Apoio B1-01
    'luana':    {'senha': os.environ.get('PASS_LUANA',    'Luana@2026'),    'nome': 'Luana',    'setores': ['B1-01']},
    'bruna':    {'senha': os.environ.get('PASS_BRUNA',    'Bruna@2026'),    'nome': 'Bruna',    'setores': ['B1-01']},
    # Injeção
    'kaline':   {'senha': os.environ.get('PASS_KALINE',   'Kaline@2026'),   'nome': 'Kaline',   'setores': ['Injecao']},
    'jocemar':  {'senha': os.environ.get('PASS_JOCEMAR',  'Jocemar@2026'),  'nome': 'Jocemar',  'setores': ['Injecao']},
    'patricia': {'senha': os.environ.get('PASS_PATRICIA', 'Patricia@2026'), 'nome': 'Patricia', 'setores': ['Injecao']},
    'tatiana':  {'senha': os.environ.get('PASS_TATIANA',  'Tatiana@2026'),  'nome': 'Tatiana',  'setores': ['Injecao']},
    'andressa': {'senha': os.environ.get('PASS_ANDRESSA', 'Andressa@2026'), 'nome': 'Andressa', 'setores': ['Injecao']},
    'kaue':     {'senha': os.environ.get('PASS_KAUE',     'Kaue@2026'),     'nome': 'Kauê',     'setores': ['Injecao']},
    'renata':   {'senha': os.environ.get('PASS_RENATA',   'Renata@2026'),   'nome': 'Renata',   'setores': ['Injecao']},
    'raquel':   {'senha': os.environ.get('PASS_RAQUEL',   'Raquel@2026'),   'nome': 'Raquel',   'setores': ['Injecao']},
    'analaura': {'senha': os.environ.get('PASS_ANALAURA', 'AnaLaura@2026'), 'nome': 'Ana Laura', 'setores': ['Injecao']},
}

SETORES = {
    'B2-03':   {'nome': 'Apoio B2-03', 'cor': '#2563EB', 'colaboradores': {'Juliana': 30, 'Sirlei': 30, 'Danmari': 29, 'Maria': 29}, 'campos_executor': ['Executor', 'Executor do teste', 'Nome do Inspetor', 'Nome do inspetor']},
    'B1-01':   {'nome': 'Apoio B1-01', 'cor': '#059669', 'colaboradores': {'Luana': 28, 'Bruna': 27},
                   'campos_executor': ['Responsável pela conferência', 'Executor', 'Executor do teste', 'Nome do Inspetor', 'Nome do inspetor'],
                   'campo_atividade': 'Etapa Auditada',
                   'campo_tipo': 'Etapa Auditada',
                   'tipo_no_campo_atividade': True,
                   'tipos_map': {
                       'completa': 'Inspeção Completa Diária',
                       'rotina':   'Inspeção de Rotina',
                       'conferência': 'Conferência e Aprovação de Cabos',
                       'conferencia': 'Conferência e Aprovação de Cabos',
                   }},
    'Injecao': {
        'nome': 'Injeção', 'cor': '#7C3AED',
        'campos_executor': ['Executor', 'Nome do inspetor', 'Nome do Inspetor'],
        'campo_atividade': 'Máquina',
        'campo_tipo': 'Tipo de inspeção',
        'tipos_map': {
            'completa':   'Inspeção Completa Diária',
            'rotina':     'Inspeção de Rotina',
            'início':     'Inspeção de Início de Produção',
            'inicio':     'Inspeção de Início de Produção',
        },

        'colaboradores': {
            # Turno 1 — 05:20 às 15:08 — meta 20
            'Kaline':   20,
            'Jocemar':  20,
            'Patricia': 20,
            # Turno 2 — 15:00 às 00:27 — meta 18
            'Tatiana':  18,
            'Andressa': 18,
            'Kaue':     18,
            # Turno 3 — 00:12 às 05:48 — meta 11
            'Renata':   11,
            'Raquel':   11,
            'Ana Laura': 11,
        },
        'nomes_map': {
            'kaline':    'Kaline',
            'jocemar':   'Jocemar',
            'patricia':  'Patricia',
            'patrica':   'Patricia',
            'tatiana':   'Tatiana',
            'andressa':  'Andressa',
            'kaue':      'Kaue',
            'kau':       'Kaue',
            'renata':    'Renata',
            'raquel':    'Raquel',
            'ana laura': 'Ana Laura',
            'ana':        'Ana Laura',
        },
        'campo_tipo': 'Tipo de inspeção',
        'tipos_map': {
            'completa':   'Inspeção Completa Diária',
            'rotina':     'Inspeção de Rotina',
            'início':     'Inspeção de Início de Produção',
            'inicio':     'Inspeção de Início de Produção',
        },
    },
}

def load_data():
    local_data = None
    github_data = None
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE) as f:
                local_data = json.load(f)
    except: pass
    if GITHUB_TOKEN and GITHUB_REPO:
        try:
            r = requests.get(
                f'https://api.github.com/repos/{GITHUB_REPO}/contents/data.json',
                headers={'Authorization': f'token {GITHUB_TOKEN}'}, timeout=8)
            if r.status_code == 200:
                github_data = json.loads(base64.b64decode(r.json()['content']).decode())
        except: pass
    base = {'B2-03': {}, 'B1-01': {}, 'Injecao': {}}
    for source in [github_data, local_data]:
        if source:
            for setor, dias in source.items():
                if setor not in base:
                    base[setor] = {}
                base[setor].update(dias)
    return base


def cf_headers():
    return {'Authorization': f'Bearer {CF_API_KEY}', 'Content-Type': 'application/json'}

def cf_buscar_avaliacoes(data_str):
    """Busca avaliações concluídas do dia data_str (YYYY-MM-DD)."""
    try:
        url = f'{CF_API_ANALYTICS}/v1/evaluations'
        headers = cf_headers()
        todas = []
        page = 1
        while True:
            r = requests.get(url, headers=headers,
                params={'status': 6, 'limit': 1000, 'page': page}, timeout=30)
            if r.status_code != 200:
                print(f'CF erro {r.status_code}: {r.text[:200]}')
                break
            resp = r.json()
            items = resp.get('data', [])
            if not items:
                break
            # Filtrar pelo dia desejado
            for item in items:
                started = str(item.get('startedAt', '') or '')
                concluded = str(item.get('concludedAt', '') or '')
                if data_str in started or data_str in concluded:
                    todas.append(item)
                elif todas:
                    # Se já achou registros do dia e agora não tem mais, parar
                    break
            if len(items) < 1000:
                break
            page += 1
        print(f'CF: {len(todas)} avaliações encontradas para {data_str}')
        return todas
    except Exception as e:
        print(f'Erro CF: {e}'); return None


def cf_buscar_resultado(eval_id):
    try:
        url = f'{CF_API_ANALYTICS}/v1/evaluations/{eval_id}/items'
        r = requests.get(url, headers=cf_headers(), timeout=30)
        if r.status_code == 200:
            return r.json()
        # Tentar endpoint alternativo
        url2 = f'{CF_API_ANALYTICS}/v1/evaluations/{eval_id}'
        r2 = requests.get(url2, headers=cf_headers(), timeout=30)
        return r2.json() if r2.status_code == 200 else None
    except: return None

def cf_sincronizar_dia(data_str):
    if not CF_API_KEY:
        return None, 'CHECKLISTFACIL_API_KEY nao configurada'
    resp = cf_buscar_avaliacoes(data_str)
    if resp is None:
        if not CF_API_KEY:
            return None, 'API key nao configurada no Render'
        return None, f'Erro ao acessar API do Checklist Facil (URL: {CF_API_URL}/evaluations)'
    
    avaliacoes = resp if isinstance(resp, list) else resp.get('data', [])
    if not avaliacoes:
        return {}, 'Nenhuma avaliacao encontrada para esta data'

    db = load_data()
    total_processado = 0
    setores_atualizados = set()

    for aval in avaliacoes:
        eval_id = aval.get('id')
        items_resp = cf_buscar_resultado(eval_id) if eval_id else None
        if not items_resp: continue
        items = items_resp.get('data', items_resp) if isinstance(items_resp, dict) else items_resp

        # Tentar extrair executor direto da avaliação (campo user/responsible)
        executor_direto = None
        user = aval.get('user') or aval.get('responsible') or aval.get('executor') or {}
        if isinstance(user, dict):
            executor_direto = user.get('name') or user.get('username') or user.get('email')
        elif isinstance(user, str):
            executor_direto = user

        dados = {}
        if items:
            items_list = items.get('data', items) if isinstance(items, dict) else items
            for item in (items_list if isinstance(items_list, list) else []):
                nome_item = str(item.get('name', '') or item.get('title', '')).strip()
                resp_item = ''
                ans = item.get('answer', item.get('response', {}))
                if isinstance(ans, dict):
                    resp_item = str(ans.get('text', '') or ans.get('value', '') or ans.get('label', '') or '').strip()
                elif isinstance(ans, str):
                    resp_item = ans.strip()
                if nome_item and resp_item:
                    dados[nome_item] = resp_item

        executor = executor_direto
        if not executor:
            for campo in ['Nome do Inspetor', 'Nome do inspetor', 'Executor', 'Nome do executor']:
                if campo in dados:
                    executor = dados[campo]; break

        atividade = None
        for campo in ['Confirme aqui o nome da maquina ou atividade', 'Etapa Auditada', 'Maquina', 'Máquina']:
            if campo in dados:
                atividade = dados[campo]; break

        checklist_nome = str(aval.get('checklist', {}).get('name', '') or
                           aval.get('checklistName', '') or '').upper()
        setor_key = None
        if 'B2-03' in checklist_nome or 'APOIO F' in checklist_nome:
            setor_key = 'B2-03'
        elif 'B1-01' in checklist_nome or 'CABOS' in checklist_nome or 'PINOS' in checklist_nome:
            setor_key = 'B1-01'
        elif 'INJECAO' in checklist_nome or 'INJEC' in checklist_nome or 'PADR' in checklist_nome:
            setor_key = 'Injecao'

        if not setor_key or not executor: continue
        nome_norm = norm_name(executor, setor_key)
        if not nome_norm: continue
        if not atividade:
            atividade = aval.get('checklist', {}).get('name', 'Sem atividade')

        meta = SETORES[setor_key]['colaboradores'].get(nome_norm, 0)
        if data_str not in db[setor_key]:
            db[setor_key][data_str] = {}
        if nome_norm not in db[setor_key][data_str]:
            db[setor_key][data_str][nome_norm] = {'meta': meta, 'total': 0, 'nc': 0, 'teste': 0, 'inspecoes': [], 'tipos': {}}

        db[setor_key][data_str][nome_norm]['total'] += 1
        db[setor_key][data_str][nome_norm]['inspecoes'].append({
            'at': atividade, 'ex': nome_norm, 'cf': None, 'tipo': None,
            'ini': aval.get('startDate'), 'fim': aval.get('endDate'), 'dur': None
        })
        setores_atualizados.add(setor_key)
        total_processado += 1

    if setores_atualizados:
        save_data(db)
    return {'setores': list(setores_atualizados), 'total': total_processado}, None

def save_data(data):
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f, ensure_ascii=False, default=str)
    except: pass
    if GITHUB_TOKEN and GITHUB_REPO:
        for tentativa in range(3):
            try:
                encoded = base64.b64encode(json.dumps(data, ensure_ascii=False, default=str).encode()).decode()
                r = requests.get(
                    f'https://api.github.com/repos/{GITHUB_REPO}/contents/data.json',
                    headers={'Authorization': f'token {GITHUB_TOKEN}'}, timeout=8)
                sha = r.json().get('sha', '') if r.status_code == 200 else ''
                payload = {
                    'message': f'update {datetime.now().strftime("%Y-%m-%d %H:%M")}',
                    'content': encoded
                }
                if sha: payload['sha'] = sha
                resp = requests.put(
                    f'https://api.github.com/repos/{GITHUB_REPO}/contents/data.json',
                    headers={'Authorization': f'token {GITHUB_TOKEN}'},
                    json=payload, timeout=15)
                if resp.status_code in (200, 201):
                    break
            except: pass

def norm_name(n, setor_key):
    if not n: return None
    s = str(n).strip()
    setor = SETORES[setor_key]
    # Para Injeção: usar mapa de nomes completos → nome curto
    if setor_key == 'Injecao':
        s_lower = s.lower().replace('ê','e').replace('á','a').replace('ã','a')
        nomes_map = setor.get('nomes_map', {})
        for chave, nome_curto in nomes_map.items():
            if chave in s_lower:
                return nome_curto
        return None
    # Para outros setores: verificar se nome do colaborador está na string
    for nome in setor.get('colaboradores', {}):
        if nome.lower() in s.lower(): return nome
    return None

def get_meta(nome, setor_key):
    return SETORES[setor_key]['colaboradores'].get(nome, 0)

def parse_xlsx(file_bytes, setor_key):
    try: df = pd.read_excel(BytesIO(file_bytes))
    except Exception as e: return None, None, str(e)
    setor_cfg = SETORES[setor_key]
    campos_exec = setor_cfg['campos_executor']
    campo_at = setor_cfg.get('campo_atividade', 'Confirme aqui o nome da máquina ou atividade')
    campo_cf = setor_cfg.get('campo_conformidade', 'Todos os itens avaliados apresentaram-se conformes?')
    valor_nc = setor_cfg.get('valor_nc', 'Não')
    by_code = {}
    for _, row in df.iterrows():
        cod = row.get('Código da avaliação')
        if cod is None or (isinstance(cod, float) and pd.isna(cod)): continue
        cod = str(cod)
        if cod not in by_code: by_code[cod] = {'at': None, 'ex': None, 'cf': None, 'ini': None, 'fim': None, 'tipo': None, 'checklist': None}
        item = str(row.get('Item', '') or '').strip()
        resp = str(row.get('Resposta', '') or '').strip()
        if item == campo_at:
            by_code[cod]['at'] = resp
            # Para setores onde o tipo está embutido no campo atividade (ex: B1-01)
            if setor_cfg.get('tipo_no_campo_atividade'):
                tipos_map = setor_cfg.get('tipos_map', {})
                resp_up = resp.upper()
                tipo_encontrado = None
                for chave, tipo_nome in tipos_map.items():
                    if chave.upper() in resp_up:
                        tipo_encontrado = tipo_nome
                        # Limpar nome da atividade removendo o sufixo do tipo
                        for sufixo in [' - INSPEÇÃO COMPLETA DIÁRIA', ' - INSPEÇÃO DE ROTINA',
                                       ' -  INSPEÇÃO COMPLETA DIÁRIA', ' -  INSPEÇÃO DE ROTINA']:
                            if sufixo.upper() in resp_up:
                                by_code[cod]['at'] = resp[:resp.upper().index(sufixo.upper())].strip()
                        break
                by_code[cod]['tipo'] = tipo_encontrado or resp
        # Ler tipo de inspeção se configurado em campo separado
        campo_tipo = setor_cfg.get('campo_tipo', '')
        if campo_tipo and not setor_cfg.get('tipo_no_campo_atividade') and item == campo_tipo:
            by_code[cod]['tipo'] = resp
        # Guardar nome do checklist para usar como atividade quando campo_at não estiver presente
        checklist_nome = row.get('Checklist', '')
        if checklist_nome and not by_code[cod].get('checklist'):
            by_code[cod]['checklist'] = str(checklist_nome)
        if item in campos_exec:
            n = norm_name(resp, setor_key)
            if n: by_code[cod]['ex'] = n
        if item == campo_cf: by_code[cod]['cf'] = resp
        ini = row.get('Data inicial'); fim = row.get('Data final')
        if not by_code[cod]['ini'] and ini is not None and str(ini) not in ('', 'nan'): by_code[cod]['ini'] = ini
        if fim is not None and str(fim) not in ('', 'nan'): by_code[cod]['fim'] = fim
    # Usar checklist como fallback de atividade quando campo_at não estiver preenchido
    for o in by_code.values():
        if not o['at'] and o.get('checklist'):
            o['at'] = o['checklist']
        # Para Injeção/B1-01: aceitar inspeções sem atividade — registrar como "Sem máquina informada"
        if setor_key in ('Injecao', 'B1-01') and not o['at'] and o.get('ex'):
            o['at'] = 'Sem máquina informada'

    inspecoes = []
    for o in by_code.values():
        if not o['ex'] or not o['at']: continue
        try:
            ini = pd.to_datetime(o['ini'], dayfirst=True) if o['ini'] is not None else None
            fim = pd.to_datetime(o['fim'], dayfirst=True) if o['fim'] is not None else None
            dur = round((fim - ini).total_seconds() / 60, 2) if ini and fim and fim > ini else None
            # Normalizar tipo de inspeção
            tipo_raw = o.get('tipo') or ''
            tipo_norm = None
            tipos_map = setor_cfg.get('tipos_map', {})
            if tipo_raw:
                tipo_lower = tipo_raw.lower().replace('ê','e').replace('í','i')
                for chave, tipo_nome in tipos_map.items():
                    if chave in tipo_lower:
                        tipo_norm = tipo_nome
                        break
                if not tipo_norm:
                    tipo_norm = tipo_raw  # manter original se não mapeado
            inspecoes.append({'at': o['at'], 'ex': o['ex'], 'cf': o['cf'], 'tipo': tipo_norm, 'ini': ini.strftime('%Y-%m-%dT%H:%M:%S') if ini else None, 'fim': fim.strftime('%Y-%m-%dT%H:%M:%S') if fim else None, 'dur': dur})
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
        if ins['cf'] == valor_nc: colaboradores[p]['nc'] += 1
        if not ins['cf']: colaboradores[p]['teste'] += 1
        # Contagem por tipo
        tipo = ins.get('tipo')
        if tipo:
            if 'tipos' not in colaboradores[p]: colaboradores[p]['tipos'] = {}
            colaboradores[p]['tipos'][tipo] = colaboradores[p]['tipos'].get(tipo, 0) + 1
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
    <button id="syncbtn" onclick="cfSync()" style="margin-left:auto;padding:7px 14px;background:#2563EB;color:#fff;border:none;border-radius:8px;font-size:12px;font-weight:600;cursor:pointer;">&#8635; Sincronizar</button>
    <span id="synctxt" style="font-size:11px;color:#718096;padding:0 6px;"></span>
    <button class="tab" id="ti" onclick="gt(4)" style="margin-left:0">Importar</button>
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

function bCard(nome,d,sk,dk){
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
  if(d.nc>0||nc>0){h+='<div class="nc"><span style="color:var(--mu)">NCs</span><span class="'+(nc>0?'nb':'ng')+'">'+nc+' NC'+(nc!==1?'s':'')+'</span></div>';}
  if(d.tipos&&Object.keys(d.tipos).length>0){
    h+='<div style="border-top:1px solid var(--bd);padding-top:.5rem;margin-top:.5rem;font-size:11px;">';
    Object.entries(d.tipos).sort().forEach(function(e){
      var label=e[0].replace('Inspeção ','').replace('de ','').replace('Diária','').replace('Produção','Início Prod.').trim();
      h+='<div style="display:flex;justify-content:space-between;margin-bottom:2px;"><span style="color:var(--mu)">'+label+'</span><span style="font-weight:600;">'+e[1]+'</span></div>';
    });
    h+='</div>';
  }
  // Exibir justificativa para gestores (TEM_TODOS) quando abaixo de 85%
  if(typeof TEM_TODOS!=="undefined" && TEM_TODOS && pct<85 && sk && dk){
    var jtxt=JUST[sk]&&JUST[sk][nome]&&JUST[sk][nome][dk]?JUST[sk][nome][dk]:null;
    if(jtxt){
      h+='<div style="border-top:1px solid #FCA5A5;margin-top:.5rem;padding:.5rem;background:#FEF2F2;border-radius:0 0 10px 10px;font-size:11px;">';
      h+='<div style="font-weight:700;color:#991B1B;margin-bottom:2px;">Justificativa:</div>';
      h+='<div style="color:#7F1D1D;">'+jtxt+'</div></div>';
    } else {
      h+='<div style="border-top:1px solid #FCA5A5;margin-top:.5rem;padding:.5rem .75rem;font-size:11px;color:#991B1B;font-weight:600;">&#9888; Justificativa pendente</div>';
    }
  }
  h+='</div>';
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
  col.forEach(function(n){ h+=bCard(n,sd[n],sk,dk); });
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

var JUST={}, TEM_TODOS=true;
var CF_SYNC_INTERVAL = null;

async function cfSync(auto){
  var btn=document.getElementById('syncbtn');
  var txt=document.getElementById('synctxt');
  if(btn){btn.disabled=true; btn.textContent='Sincronizando...';}
  if(txt) txt.textContent='';
  try{
    var hoje=new Date();
    var dk=hoje.getFullYear()+'-'+String(hoje.getMonth()+1).padStart(2,'0')+'-'+String(hoje.getDate()).padStart(2,'0');
    var r=await fetch('/api/cf/sync',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({data:dk})});
    var d=await r.json();
    if(d.ok){
      var res=d.resultado||{};
      var msg=auto?'Auto: ':'';
      if(txt) txt.textContent=msg+'Atualizado '+new Date().toLocaleTimeString('pt-BR',{hour:'2-digit',minute:'2-digit'})+' ('+( res.total||0)+' insp)';
      await loadDB();
    } else {
      if(txt) txt.textContent='Erro: '+(d.erro||'falha na sincronização');
    }
  }catch(e){
    if(txt) txt.textContent='Erro de conexão';
  }
  if(btn){btn.disabled=false; btn.textContent='↻ Sincronizar';}
}

function iniciarAutoSync(intervalo_min){
  if(CF_SYNC_INTERVAL) clearInterval(CF_SYNC_INTERVAL);
  CF_SYNC_INTERVAL=setInterval(function(){ cfSync(true); }, intervalo_min*60*1000);
}

async function loadDB(){
  try{
    var r=await fetch('/api/data');DB=await r.json();
    var rj=await fetch('/api/justificativas');JUST=await rj.json();
    var n=SK.reduce(function(a,sk){return a+Object.keys(DB[sk]||{}).length;},0);
    document.getElementById('nfo').textContent=n+' dias registrados';
    rAll();
  }catch(e){document.getElementById('nfo').textContent='Erro ao carregar';}
  // Iniciar auto-sync a cada 5 minutos
  iniciarAutoSync(5);
}

loadDB();
</script>
</body>
</html>'''

@app.route('/b2-03')
def page_b203():
    return Response(get_setor_html('B2-03', 'Apoio B2-03', '#2563EB'), mimetype='text/html')

@app.route('/b1-01')
def page_b101():
    return Response(get_setor_html('B1-01', 'Apoio B1-01', '#059669'), mimetype='text/html')

@app.route('/injecao')
def page_injecao():
    return Response(get_setor_html('Injecao', 'Injeção', '#7C3AED'), mimetype='text/html')

def get_setor_html(setor_key, setor_nome, setor_cor):
    return '''<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>''' + setor_nome + ''' - Controle de Inspecoes</title>
<style>
:root{--bg:#F0F4F8;--wh:#fff;--bd:#E2E8F0;--tx:#1A202C;--mu:#718096;--gr:#059669;--am:#D97706;--rd:#DC2626;--gr2:#ECFDF5;--am2:#FFFBEB;--rd2:#FEF2F2}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;background:var(--bg);color:var(--tx);min-height:100vh}
.top{background:''' + setor_cor + ''';color:#fff;padding:.85rem 1.5rem;display:flex;justify-content:space-between;align-items:center}
.top h1{font-size:18px;font-weight:700}
.top p{font-size:11px;opacity:.85;margin-top:2px}
.main{max-width:1100px;margin:0 auto;padding:1.5rem}
.dsel{display:flex;align-items:center;gap:10px;margin-bottom:1.5rem}
.dsel select{flex:1;padding:9px 12px;border:1px solid var(--bd);border-radius:8px;font-size:14px;background:var(--wh);color:var(--tx);font-family:inherit}
.sl{font-size:11px;font-weight:700;color:var(--mu);text-transform:uppercase;letter-spacing:.06em;white-space:nowrap}
.kg{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:12px;margin-bottom:1.5rem}
.kc{background:var(--wh);border:1px solid var(--bd);border-radius:10px;padding:14px 16px}
.kl{font-size:11px;color:var(--mu);text-transform:uppercase;letter-spacing:.05em;margin-bottom:.35rem}
.kv{font-size:26px;font-weight:700}
.ks{font-size:11px;color:var(--mu);margin-top:.2rem}
.cg{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px}
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
.empty{text-align:center;padding:4rem;color:var(--mu);font-size:14px}
.loading{text-align:center;padding:4rem;color:var(--mu);font-size:14px}
.nav-back{display:inline-flex;align-items:center;gap:6px;font-size:12px;color:rgba(255,255,255,.8);text-decoration:none;margin-top:4px}
.nav-back:hover{color:#fff}
.date-nav{display:flex;gap:8px;align-items:center}
.nav-btn{padding:6px 12px;border:1px solid var(--bd);border-radius:6px;background:var(--wh);font-size:12px;cursor:pointer;font-family:inherit;color:var(--tx)}
.nav-btn:hover{background:var(--bg)}
</style>
</head>
<body>
<div class="top">
  <div>
    <h1>''' + setor_nome + '''</h1>
    <p>Zagonel - Controle de Qualidade</p>
  </div>
  <div id="nfo" style="font-size:12px;opacity:.8">Carregando...</div>
</div>
<div class="main">
  <div id="content"><div class="loading">Carregando dados...</div></div>
</div>
<script>
var DB = {};
var SK = "''' + setor_key + '''";
var COR = "''' + setor_cor + '''";

function fD(k){ var d=new Date(k+"T12:00:00"); return pad(d.getDate())+"/"+pad(d.getMonth()+1)+"/"+d.getFullYear(); }
function pad(n){ return n<10?"0"+n:""+n; }
function cl(p,t){ if(!t)return"em"; if(p<85)return"no"; if(p<=100)return"at"; return"sv"; }
function pt(c){ return c==="sv"?"Superou":c==="at"?"Atingiu a meta":c==="no"?"Nao atingiu":"Sem dados"; }

function render(dk){
  var el=document.getElementById("content");
  var sd=(DB[SK]||{})[dk]||{};
  var col=Object.keys(sd);
  if(!col.length){el.innerHTML="<div class=\"empty\">Sem dados para esta data.</div>";return;}
  var tot=0,meta=0,nc=0,nsv=0,nat=0,nno=0;
  col.forEach(function(n){var d=sd[n];tot+=d.total;if(d.total>0)meta+=d.meta;nc+=d.nc;var p=d.meta>0?Math.round(d.total/d.meta*100):0,c=cl(p,d.total);if(c==="sv")nsv++;else if(c==="at")nat++;else if(c==="no")nno++;});
  var pct=meta>0?Math.round(tot/meta*100):0;
  var dias=Object.keys(DB[SK]||{}).sort(function(a,b){return b.localeCompare(a);});
  var h="<div class=\"dsel\"><span class=\"sl\">Data</span><select id=\"ds\" onchange=\"goDay(this.value)\">";
  dias.forEach(function(d){h+="<option value=\""+d+"\""+( d===dk?" selected":"")+">"+fD(d)+"</option>";});
  h+="</select></div>";
  h+="<div class=\"kg\">";
  h+="<div class=\"kc\"><div class=\"kl\">Inspecoes</div><div class=\"kv\">"+tot+"</div><div class=\"ks\">meta: "+meta+"</div></div>";
  h+="<div class=\"kc\"><div class=\"kl\">% da meta</div><div class=\"kv\" style=\"color:"+(pct>=100?"var(--gr)":pct>=85?"var(--am)":"var(--rd)")+"\">"+pct+"%</div></div>";
  h+="<div class=\"kc\"><div class=\"kl\">Status da equipe</div><div class=\"kv\" style=\"font-size:13px;line-height:1.8\">";
  if(nsv>0)h+="<span style=\"color:var(--gr)\">"+nsv+" superou</span><br>";
  if(nat>0)h+="<span style=\"color:var(--am)\">"+nat+" atingiu</span><br>";
  if(nno>0)h+="<span style=\"color:var(--rd)\">"+nno+" abaixo</span>";
  h+="</div></div></div>";
  h+="<div class=\"cg\">";
  col.forEach(function(nome){
    var d=sd[nome];
    var tot2=d.total||0,meta2=d.meta||0,nc2=d.nc||0;
    var pct2=meta2>0?Math.round(tot2/meta2*100):0,c=cl(pct2,tot2);
    h+="<div class=\"card "+c+"\"><div class=\"cn\">"+nome+"</div><div class=\"cm\">Meta: "+meta2+" inspecoes/dia</div>";
    h+="<div class=\"cp\">"+(!tot2?"--":pct2+"%")+"</div>";
    h+="<div class=\"cs\">"+(!tot2?"Sem registros":tot2+" realizadas - meta "+meta2)+"</div>";
    h+="<div class=\"bar\"><div class=\"bf\" style=\"width:"+(!tot2?0:Math.min(pct2,100))+"%\"></div></div>";
    h+="<div class=\"cst\"><div><div class=\"cv\">"+tot2+"</div><div class=\"cl2\">realizadas</div></div>";
    h+="<div><div class=\"cv\">"+(tot2-nc2)+"</div><div class=\"cl2\">conformes</div></div>";
    h+="<div><div class=\"cv\">"+meta2+"</div><div class=\"cl2\">meta</div></div></div>";
    h+="<span class=\"pill\">"+pt(c)+"</span>";
    if(d.tipos&&Object.keys(d.tipos).length>0){";
    h+="<div style=\"border-top:1px solid var(--bd);padding-top:.5rem;margin-top:.5rem;font-size:11px;\">";
    Object.entries(d.tipos).sort().forEach(function(e){";
      var label=e[0].replace("Inspecao ","").replace("Inspeção ","").replace("de ","").replace("Diária","").replace("Producao","Início Prod.").replace("Produção","Início Prod.").trim();
      h+="<div style=\"display:flex;justify-content:space-between;margin-bottom:2px;\"><span style=\"color:var(--mu)\">"+label+"</span><span style=\"font-weight:600;\">"+e[1]+"</span></div>";
    });
    h+="</div>";
    }
    h+="</div>";
  });
  h+="</div>";
  el.innerHTML=h;
}

function goDay(dk){ render(dk); }

async function loadDB(){
  try{
    var r=await fetch("/api/data");
    DB=await r.json();
    var dias=Object.keys(DB[SK]||{}).sort(function(a,b){return b.localeCompare(a);});
    var n=dias.length;
    document.getElementById("nfo").textContent=n+(n===1?" dia registrado":" dias registrados");
    if(dias.length) render(dias[0]);
    else document.getElementById("content").innerHTML="<div class=\"empty\">Nenhum dado importado ainda.</div>";
  }catch(e){
    document.getElementById("nfo").textContent="Erro ao carregar";
  }
}
loadDB();
</script>
</body>
</html>''';

if __name__ == '__main__':
    app.run(debug=True)

@app.route('/api/cf/sync', methods=['POST'])
def api_cf_sync():
    body = request.get_json() or {}
    data_str = body.get('data')
    if not data_str:
        from datetime import date
        data_str = date.today().strftime('%Y-%m-%d')
    resultado, erro = cf_sincronizar_dia(data_str)
    if erro and not resultado:
        return jsonify({'ok': False, 'erro': erro}), 400
    return jsonify({'ok': True, 'resultado': resultado, 'aviso': erro})

@app.route('/api/cf/status')
def api_cf_status():
    if not CF_API_KEY:
        return jsonify({'ok': False, 'erro': 'API key nao configurada (CHECKLISTFACIL_API_KEY)'})
    from datetime import date
    hoje = date.today().strftime('%Y-%m-%d')
    url = f'{CF_API_ANALYTICS}/v1/evaluations'
    try:
        r = requests.get(url, headers=cf_headers(),
            params={'status': 6, 'limit': 3, 'page': 1}, timeout=10)
        if r.status_code == 200:
            data = r.json()
            items = data.get('data', [])
            sample = items[0] if items else {}
            return jsonify({
                'ok': True,
                'total_amostra': len(items),
                'campos_disponiveis': list(sample.keys()),
                'exemplo': sample
            })
        return jsonify({'ok': False, 'status': r.status_code, 'body': r.text[:200]})
    except Exception as e:
        return jsonify({'ok': False, 'erro': str(e)})


@app.route('/api/me')
def api_me():
    if not session.get('usuario'):
        return jsonify({'error': 'Nao autenticado'}), 401
    usuario = session.get('usuario', '')
    info = USUARIOS.get(usuario, {})
    return jsonify({
        'nome': info.get('nome', usuario),
        'setores': info.get('setores', []),
        'tem_todos': len(info.get('setores', [])) > 1
    })

@app.route('/api/justificativas')
def api_justificativas():
    db = load_data()
    return jsonify(db.get('justificativas', {}))

@app.route('/api/justificativa', methods=['POST'])
def api_salvar_justificativa():
    if not session.get('usuario'):
        return jsonify({'error': 'Nao autenticado'}), 401
    data = request.get_json() or {}
    setor = data.get('setor')
    colab = data.get('colaborador')
    dia   = data.get('data')
    texto = data.get('texto', '').strip()
    if not all([setor, colab, dia, texto]):
        return jsonify({'error': 'Dados incompletos'}), 400
    db = load_data()
    if 'justificativas' not in db: db['justificativas'] = {}
    if setor not in db['justificativas']: db['justificativas'][setor] = {}
    if colab not in db['justificativas'][setor]: db['justificativas'][setor][colab] = {}
    db['justificativas'][setor][colab][dia] = texto
    save_data(db)
    return jsonify({'ok': True})

@app.route('/login', methods=['GET','POST'])
def login():
    erro = ''
    if request.method == 'POST':
        usuario = request.form.get('usuario','').strip().lower()
        senha   = request.form.get('senha','').strip()
        if usuario in USUARIOS and USUARIOS[usuario]['senha'] == senha:
            session['usuario']  = usuario
            session['nome']     = USUARIOS[usuario]['nome']
            session['setores']  = USUARIOS[usuario]['setores']
            return redirect('/painel')
        erro = 'Usuário ou senha incorretos.'
    return Response(get_login_html(erro), mimetype='text/html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/painel')
def page_painel():
    if not session.get('usuario'):
        return redirect('/login')
    return Response(get_painel_html(
        session.get('nome',''),
        session.get('setores', [])
    ), mimetype='text/html')

@app.route('/monitor')
def page_monitor():
    if not session.get('monitor_ok') and not session.get('usuario'):
        return redirect('/login')
    return redirect('/painel')

def get_painel_html(nome_usuario, setores_permitidos):
    SN = {'B2-03':'Apoio B2-03','B1-01':'Apoio B1-01','Injecao':'Injecao'}
    SC = {'B2-03':'#2563EB','B1-01':'#059669','Injecao':'#7C3AED'}
    setores_js = str(setores_permitidos).replace("'",'"')
    sn_js = str({k: SN[k] for k in setores_permitidos if k in SN}).replace("'",'"')
    sc_js = str({k: SC[k] for k in setores_permitidos if k in SC}).replace("'",'"')
    tem_todos = len(setores_permitidos) > 1
    return """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Painel - Zagonel</title>
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
#tt.on{background:#334155}
#tb1.on{background:#2563EB}
#tb2.on{background:#059669}
#tb3.on{background:#7C3AED}
.pg{display:none}.pg.on{display:block}
.dsel{display:flex;align-items:center;gap:10px;margin-bottom:1.5rem}
.dsel select{flex:1;padding:9px 12px;border:1px solid var(--bd);border-radius:8px;font-size:14px;background:var(--wh);color:var(--tx);font-family:inherit}
.sl{font-size:11px;font-weight:700;color:var(--mu);text-transform:uppercase;letter-spacing:.06em;white-space:nowrap}
.sb{margin-bottom:2rem}
.sh{display:flex;align-items:center;gap:8px;margin-bottom:1rem}
.sd{width:12px;height:12px;border-radius:3px}
.st{font-size:16px;font-weight:700}
.ss{font-size:12px;color:var(--mu);margin-left:auto}
.kg{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:10px;margin-bottom:1.25rem}
.kc{background:var(--wh);border:1px solid var(--bd);border-radius:10px;padding:12px 14px}
.kl{font-size:10px;color:var(--mu);text-transform:uppercase;letter-spacing:.05em;margin-bottom:.3rem}
.kv{font-size:24px;font-weight:700}
.ks{font-size:11px;color:var(--mu);margin-top:.2rem}
.cg{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}
.card{background:var(--wh);border:1px solid var(--bd);border-radius:12px;padding:1.1rem;position:relative;overflow:hidden}
.card::before{content:"";position:absolute;top:0;left:0;right:0;height:4px;border-radius:12px 12px 0 0}
.sv::before{background:var(--gr)}.at::before{background:var(--am)}.no::before{background:var(--rd)}.em::before{background:var(--bd)}
.cn{font-size:11px;font-weight:700;color:var(--mu);text-transform:uppercase;letter-spacing:.06em;margin-bottom:.2rem}
.cm{font-size:11px;color:var(--mu);margin-bottom:.6rem}
.cp{font-size:38px;font-weight:700;line-height:1;margin-bottom:.15rem}
.sv .cp{color:var(--gr)}.at .cp{color:var(--am)}.no .cp{color:var(--rd)}.em .cp{color:#CBD5E0}
.cs{font-size:11px;color:var(--mu);margin-bottom:.6rem}
.bar{height:4px;background:#EDF2F7;border-radius:3px;margin-bottom:.75rem;overflow:hidden}
.bf{height:4px;border-radius:3px}
.sv .bf{background:var(--gr)}.at .bf{background:var(--am)}.no .bf{background:var(--rd)}.em .bf{background:#CBD5E0}
.cst{display:grid;grid-template-columns:repeat(3,1fr);border-top:1px solid var(--bd);padding-top:.6rem}
.cv{font-size:16px;font-weight:700;text-align:center}
.cl2{font-size:10px;color:var(--mu);text-align:center;margin-top:1px}
.pill{display:inline-flex;align-items:center;gap:4px;font-size:10px;font-weight:600;padding:2px 8px;border-radius:20px;margin-top:.5rem}
.sv .pill{background:var(--gr2);color:var(--gr)}.at .pill{background:var(--am2);color:var(--am)}.no .pill{background:var(--rd2);color:var(--rd)}.em .pill{background:#F7FAFC;color:var(--mu)}
.div{border:none;border-top:1px solid var(--bd);margin:1.5rem 0}
.empty{text-align:center;padding:3rem;color:var(--mu);font-size:13px}
.sair{font-size:11px;color:rgba(255,255,255,.85);text-decoration:none;border:1px solid rgba(255,255,255,.4);padding:4px 12px;border-radius:6px}
.sair:hover{background:rgba(255,255,255,.15)}
</style>
</head>
<body>
<div class="top">
  <div>
    <h1>Controle de Inspecoes</h1>
    <p>Ola, """ + nome_usuario + """ &middot; Zagonel Qualidade Industrial</p>
  </div>
  <div style="display:flex;align-items:center;gap:12px">
    <div id="nfo" style="font-size:12px;opacity:.8">Carregando...</div>
    <a href="/logout" class="sair">Sair</a>
  </div>
</div>
<div class="main">
  <div id="content">
    <div class="tabs" id="tabs"></div>
    <div id="pg-todos" class="pg on"><div id="c-todos"><div class="empty">Carregando...</div></div></div>
    <div id="pg-B2-03" class="pg"><div id="c-B2-03"></div></div>
    <div id="pg-B1-01" class="pg"><div id="c-B1-01"></div></div>
    <div id="pg-Injecao" class="pg"><div id="c-Injecao"></div></div>
  </div>
</div>
<script>
var DB={},SK=""" + setores_js + """,SN=""" + sn_js + """,SC=""" + sc_js + """,TEM_TODOS=""" + ('true' if tem_todos else 'false') + """;
function fD(k){var d=new Date(k+"T12:00:00");return pad(d.getDate())+"/"+pad(d.getMonth()+1)+"/"+d.getFullYear();}
function pad(n){return n<10?"0"+n:""+n;}
function cl(p,t){if(!t)return"em";if(p<85)return"no";if(p<=100)return"at";return"sv";}
function pt(c){return c==="sv"?"Superou":c==="at"?"Atingiu a meta":c==="no"?"Nao atingiu":"Sem dados";}
function bCard(nome,d){
  var tot=d.total||0,meta=d.meta||0,nc=d.nc||0;
  var pct=meta>0?Math.round(tot/meta*100):0,c=cl(pct,tot);
  var h='<div class="card '+c+'"><div class="cn">'+nome+'</div><div class="cm">Meta: '+meta+' inspecoes/dia</div>';
  h+='<div class="cp">'+(!tot?"--":pct+"%")+'</div>';
  h+='<div class="cs">'+(!tot?"Sem registros":tot+" realizadas - meta "+meta)+'</div>';
  h+='<div class="bar"><div class="bf" style="width:'+(!tot?0:Math.min(pct,100))+'%"></div></div>';
  h+='<div class="cst"><div><div class="cv">'+tot+'</div><div class="cl2">realizadas</div></div>';
  h+='<div><div class="cv">'+(tot-nc)+'</div><div class="cl2">conformes</div></div>';
  h+='<div><div class="cv">'+meta+'</div><div class="cl2">meta</div></div></div>';
  h+='<span class="pill">'+pt(c)+'</span>';
  if(d.tipos&&Object.keys(d.tipos).length){
    h+='<div style="border-top:1px solid var(--bd);padding-top:.5rem;margin-top:.5rem;font-size:11px;">';
    Object.entries(d.tipos).sort().forEach(function(e){
      var lb=e[0].replace("Inspeção ","").replace("de ","").replace("Diária","").replace("Produção","Início Prod.").trim();
      h+='<div style="display:flex;justify-content:space-between;margin-bottom:2px;"><span style="color:var(--mu)">'+lb+'</span><span style="font-weight:600">'+e[1]+'</span></div>';
    });
    h+="</div>";
  }
  return h+"</div>";
}
function bSetor(sk,dk){
  var sd=(DB[sk]||{})[dk]||{},col=Object.keys(sd);
  if(!col.length)return"";
  var tot=0,meta=0,nc=0,nsv=0,nat=0,nno=0;
  col.forEach(function(n){var d=sd[n];tot+=d.total;if(d.total>0)meta+=d.meta;nc+=d.nc;var p=d.meta>0?Math.round(d.total/d.meta*100):0,c=cl(p,d.total);if(c==="sv")nsv++;else if(c==="at")nat++;else if(c==="no")nno++;});
  var pct=meta>0?Math.round(tot/meta*100):0;
  var h='<div class="sb"><div class="sh"><div class="sd" style="background:'+SC[sk]+'"></div><div class="st">'+SN[sk]+'</div><div class="ss">'+tot+' insp · '+pct+'% meta</div></div>';
  h+='<div class="kg"><div class="kc"><div class="kl">Inspecoes</div><div class="kv">'+tot+'</div><div class="ks">meta: '+meta+'</div></div>';
  h+='<div class="kc"><div class="kl">% da meta</div><div class="kv" style="color:'+(pct>=100?"var(--gr)":pct>=85?"var(--am)":"var(--rd)")+'">'+pct+'%</div></div>';
  h+='<div class="kc"><div class="kl">Status</div><div class="kv" style="font-size:12px;line-height:1.8;">';
  if(nsv>0)h+='<span style="color:var(--gr)">'+nsv+' superou</span><br>';
  if(nat>0)h+='<span style="color:var(--am)">'+nat+' atingiu</span><br>';
  if(nno>0)h+='<span style="color:var(--rd)">'+nno+' abaixo</span>';
  h+='</div></div></div><div class="cg">';
  col.forEach(function(n){h+=bCard(n,sd[n],sk,dk);});
  return h+"</div></div>";
}
function getDias(sk){
  var dias=[];
  if(sk==="todos"){SK.forEach(function(s){Object.keys(DB[s]||{}).forEach(function(d){if(dias.indexOf(d)<0)dias.push(d);});});}
  else{dias=Object.keys(DB[sk]||{});}
  return dias.sort(function(a,b){return b.localeCompare(a);});
}
function rTodos(dk){
  var el=document.getElementById("c-todos");
  var dias=getDias("todos");
  if(!dias.length){el.innerHTML='<div class="empty">Nenhum dado importado.</div>';return;}
  if(!dk)dk=dias[0];
  var h='<div class="dsel"><span class="sl">Data</span><select id="sel-todos">';
  dias.forEach(function(d){h+='<option value="'+d+'"'+(d===dk?' selected':'')+'>'+fD(d)+'</option>';});
  h+='</select></div><div id="body-c-todos"></div>';
  el.innerHTML=h;
  document.getElementById("sel-todos").addEventListener("change",function(){rTodos(this.value);});
  var bod="",ok=false;
  SK.forEach(function(sk){var s=bSetor(sk,dk);if(s){bod+=s;bod+='<div class="div"></div>';ok=true;}});
  document.getElementById("body-c-todos").innerHTML=ok?bod:'<div class="empty">Sem dados para esta data.</div>';
}
function rSetor(sk,dk){
  var cid="c-"+sk,el=document.getElementById(cid);
  if(!el)return;
  var dias=getDias(sk);
  if(!dias.length){el.innerHTML='<div class="empty">Sem dados para este setor.</div>';return;}
  if(!dk)dk=dias[0];
  var h='<div class="dsel"><span class="sl">Data</span><select id="sel-'+sk+'">';
  dias.forEach(function(d){h+='<option value="'+d+'"'+(d===dk?' selected':'')+'>'+fD(d)+'</option>';});
  h+='</select></div><div id="body-'+cid+'"></div>';
  el.innerHTML=h;
  document.getElementById("sel-"+sk).addEventListener("change",(function(s){return function(){rSetor(s,this.value);};})(sk));
  document.getElementById("body-"+cid).innerHTML=bSetor(sk,dk)||'<div class="empty">Sem dados para esta data.</div>';
}
function goTab(s,btn){
  document.querySelectorAll(".tab").forEach(function(b){b.classList.remove("on");});
  btn.classList.add("on");
  document.querySelectorAll(".pg").forEach(function(p){p.classList.remove("on");});
  document.getElementById("pg-"+s).classList.add("on");
  if(s==="todos")rTodos();else rSetor(s);
}
function buildTabs(){
  var tabs=document.getElementById("tabs");tabs.innerHTML="";
  if(TEM_TODOS){
    var b=document.createElement("button");b.className="tab on";b.id="tt";b.textContent="Todos os setores";
    b.onclick=function(){goTab("todos",b);};tabs.appendChild(b);
  }
  SK.forEach(function(sk,i){
    var b=document.createElement("button");
    b.className="tab"+((!TEM_TODOS&&i===0)?" on":"");
    b.id="tb"+(i+1);b.textContent=SN[sk];
    b.style.cssText="--sc:"+SC[sk];
    b.onclick=function(){goTab(sk,b);};
    b.addEventListener("click",function(){this.style.background=SC[sk];this.style.color="#fff";this.style.borderColor="transparent";});
    tabs.appendChild(b);
  });
}
var JUST={}, _SK='', _DK='', NOME_INSP='', TEM_TODOS=false;

function getPendentes(){
  if(TEM_TODOS) return [];
  var pend=[];
  try{
    var limite=new Date(); limite.setDate(limite.getDate()-7);
    var limiteStr=limite.getFullYear()+'-'+String(limite.getMonth()+1).padStart(2,'0')+'-'+String(limite.getDate()).padStart(2,'0');
    SK.forEach(function(sk){
      Object.keys(DB[sk]||{}).forEach(function(dk){
        if(dk<limiteStr) return;
        var colab=(DB[sk][dk])||{};
        if(!colab[NOME_INSP]) return;
        var d=colab[NOME_INSP];
        var pct=d.meta>0?Math.round(d.total/d.meta*100):100;
        if(pct<85){
          var jatem=JUST[sk]&&JUST[sk][NOME_INSP]&&JUST[sk][NOME_INSP][dk];
          if(!jatem) pend.push({sk:sk,nome:NOME_INSP,dk:dk,pct:pct,tot:d.total,meta:d.meta});
        }
      });
    });
  }catch(e){console.error(e);}
  return pend.sort(function(a,b){return a.dk.localeCompare(b.dk);});
}

function mostrarBloqueio(pend){
  var p=pend[0];
  var nfo=document.getElementById("nfo");
  if(nfo) nfo.textContent="Justificativa pendente";

  // Criar overlay de justificativa sobre tudo
  var overlay=document.getElementById("joverlay");
  if(!overlay){
    overlay=document.createElement("div");
    overlay.id="joverlay";
    overlay.style.cssText="position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(240,244,248,.97);z-index:999;display:flex;align-items:center;justify-content:center;";
    document.body.appendChild(overlay);
  }
  var msg=pend.length>1?"<div style='font-size:11px;color:#718096;margin-bottom:1rem;'>Ainda há mais "+(pend.length-1)+" justificativa(s) pendente(s) após esta.</div>":"";
  overlay.innerHTML=
    "<div style='max-width:500px;width:90%;background:#fff;border-radius:12px;padding:2rem;border:1px solid #E2E8F0;box-shadow:0 8px 32px rgba(0,0,0,.1);'>"
    +"<div style='background:#FEF2F2;border-radius:8px;padding:1rem;margin-bottom:1.5rem;'>"
    +"<div style='font-size:14px;font-weight:700;color:#991B1B;margin-bottom:.4rem;'>Justificativa obrigatória</div>"
    +"<div style='font-size:13px;color:#7F1D1D;'>Você ficou com <strong>"+p.pct+"%</strong> da meta no dia <strong>"+fD(p.dk)+"</strong><br>("+p.tot+"/"+p.meta+" inspeções realizadas).</div>"
    +"</div>"
    +"<div style='font-size:13px;font-weight:700;color:#1A202C;margin-bottom:.5rem;'>Qual o motivo do resultado abaixo de 85%?</div>"
    +"<textarea id='jtexto' rows='4' placeholder='Descreva o motivo aqui...' style='width:100%;padding:10px;border:1.5px solid #E2E8F0;border-radius:8px;font-family:inherit;font-size:13px;resize:vertical;outline:none;margin-bottom:.75rem;'></textarea>"
    +msg
    +"<button id='jbtn' style='width:100%;padding:12px;background:#05B15D;color:#fff;border:none;border-radius:8px;font-size:14px;font-weight:700;cursor:pointer;font-family:inherit;'>Registrar justificativa</button>"
    +"</div>";
  document.getElementById("jbtn").onclick=function(){salvarJust(p.sk,p.nome,p.dk);};
}

async function salvarJust(sk,nome,dk){
  var texto=document.getElementById("jtexto").value.trim();
  if(!texto){alert("Por favor, descreva o motivo.");return;}
  var btn=document.getElementById("jbtn");
  if(btn){btn.disabled=true;btn.textContent="Salvando...";}
  try{
    var r=await fetch("/api/justificativa",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({setor:sk,colaborador:nome,data:dk,texto:texto})});
    var d=await r.json();
    if(d.ok){
      // Atualizar JUST local
      if(!JUST[sk])JUST[sk]={};
      if(!JUST[sk][nome])JUST[sk][nome]={};
      JUST[sk][nome][dk]=texto;
      // Recarregar justificativas do servidor para garantir persistência
      try{
        var r2=await fetch("/api/justificativas");
        JUST=await r2.json();
      }catch(e2){}
      var pend=getPendentes();
      if(pend.length){
        mostrarBloqueio(pend);
      } else {
        var overlay=document.getElementById("joverlay");
        if(overlay) overlay.remove();
        iniciarPainel();
      }
    } else {
      alert("Erro ao salvar: "+(d.error||"tente novamente."));
      if(btn){btn.disabled=false;btn.textContent="Registrar justificativa";}
    }
  }catch(e){
    alert("Erro de conexão. Tente novamente.");
    if(btn){btn.disabled=false;btn.textContent="Registrar justificativa";}
  }
}

function iniciarPainel(){
  var overlay=document.getElementById("joverlay");
  if(overlay) overlay.remove();
  var n=SK.reduce(function(a,sk){return a+Object.keys(DB[sk]||{}).length;},0);
  var nfo=document.getElementById("nfo");
  if(nfo) nfo.textContent=n+" dias registrados";
  buildTabs();
  if(TEM_TODOS)rTodos();else if(SK.length)rSetor(SK[0]);
}

async function loadDB(){
  try{
    var rm=await fetch("/api/me"); var me=await rm.json();
    if(me.error){window.location="/login";return;}
    NOME_INSP=me.nome;
    TEM_TODOS=me.tem_todos;
    SK=me.setores;
    var r1=await fetch("/api/data"); DB=await r1.json();
    var r2=await fetch("/api/justificativas"); JUST=await r2.json();
    var pend=getPendentes();
    if(pend.length) mostrarBloqueio(pend);
    else iniciarPainel();
  }catch(e){
    console.error("Erro loadDB:",e);
    var c=document.getElementById("content");
    if(c) c.innerHTML='<div class="empty">Erro ao carregar dados. Recarregue a página.</div>';
    var n=document.getElementById("nfo");
    if(n) n.textContent="Erro ao carregar";
  }
}
loadDB();
</script>
</body>
</html>""";


def get_login_html(erro=''):
    return '''<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Acesso Monitor - Zagonel</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;background:#F0F4F8;min-height:100vh;display:flex;align-items:center;justify-content:center}
.box{background:#fff;border-radius:12px;padding:2.5rem;width:100%;max-width:380px;box-shadow:0 4px 24px rgba(0,0,0,.08)}
.logo{text-align:center;margin-bottom:2rem}
.logo div{font-size:22px;font-weight:700;color:#05B15D}
.logo p{font-size:12px;color:#718096;margin-top:4px}
.fg{margin-bottom:1rem}
label{display:block;font-size:11px;font-weight:700;color:#718096;text-transform:uppercase;letter-spacing:.05em;margin-bottom:.35rem}
input{width:100%;padding:10px 14px;border:1.5px solid #E2E8F0;border-radius:8px;font-size:14px;font-family:inherit;outline:none;transition:.15s}
input:focus{border-color:#05B15D}
.btn{width:100%;padding:12px;background:#05B15D;color:#fff;border:none;border-radius:8px;font-size:15px;font-weight:700;cursor:pointer;font-family:inherit;margin-top:.5rem}
.btn:hover{background:#047a42}
.erro{background:#FEF2F2;color:#991B1B;border-radius:8px;padding:10px 14px;font-size:13px;margin-bottom:1rem;text-align:center}
</style>
</head>
<body>
<div class="box">
  <div class="logo">
    <div>Zagonel</div>
    <p>Controle de Inspecoes - Monitor</p>
  </div>
  ''' + ('<div class="erro">'+ erro +'</div>' if erro else '') + '''
  <form method="POST">
    <div class="fg">
      <label>Usuario</label>
      <input type="text" name="usuario" placeholder="Digite seu usuario" autofocus required>
    </div>
    <div class="fg">
      <label>Senha</label>
      <input type="password" name="senha" placeholder="Digite sua senha" required>
    </div>
    <button type="submit" class="btn">Entrar</button>
  </form>
</div>
</body>
</html>'''

def get_monitor_html():
    return '''<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Monitor - Controle de Inspecoes Zagonel</title>
<style>
:root{--bg:#F0F4F8;--wh:#fff;--bd:#E2E8F0;--tx:#1A202C;--mu:#718096;--gr:#059669;--am:#D97706;--rd:#DC2626;--gr2:#ECFDF5;--am2:#FFFBEB;--rd2:#FEF2F2}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;background:var(--bg);color:var(--tx);min-height:100vh}
.top{background:#05B15D;color:#fff;padding:.85rem 1.5rem;display:flex;justify-content:space-between;align-items:center}
.top h1{font-size:18px;font-weight:700}
.top p{font-size:11px;opacity:.85;margin-top:2px}
.main{max-width:1200px;margin:0 auto;padding:1.5rem}
.dsel{display:flex;align-items:center;gap:10px;margin-bottom:1.5rem}
.dsel select{flex:1;padding:9px 12px;border:1px solid var(--bd);border-radius:8px;font-size:14px;background:var(--wh);color:var(--tx);font-family:inherit}
.sl{font-size:11px;font-weight:700;color:var(--mu);text-transform:uppercase;letter-spacing:.06em;white-space:nowrap}
.sb{margin-bottom:2rem}
.sh{display:flex;align-items:center;gap:8px;margin-bottom:1rem}
.sd{width:12px;height:12px;border-radius:3px}
.st{font-size:16px;font-weight:700}
.ss{font-size:12px;color:var(--mu);margin-left:auto}
.kg{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:10px;margin-bottom:1.25rem}
.kc{background:var(--wh);border:1px solid var(--bd);border-radius:10px;padding:12px 14px}
.kl{font-size:10px;color:var(--mu);text-transform:uppercase;letter-spacing:.05em;margin-bottom:.3rem}
.kv{font-size:24px;font-weight:700}
.ks{font-size:11px;color:var(--mu);margin-top:.2rem}
.cg{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}
.card{background:var(--wh);border:1px solid var(--bd);border-radius:12px;padding:1.1rem;position:relative;overflow:hidden}
.card::before{content:"";position:absolute;top:0;left:0;right:0;height:4px;border-radius:12px 12px 0 0}
.sv::before{background:var(--gr)}.at::before{background:var(--am)}.no::before{background:var(--rd)}.em::before{background:var(--bd)}
.cn{font-size:11px;font-weight:700;color:var(--mu);text-transform:uppercase;letter-spacing:.06em;margin-bottom:.2rem}
.cm{font-size:11px;color:var(--mu);margin-bottom:.6rem}
.cp{font-size:38px;font-weight:700;line-height:1;margin-bottom:.15rem}
.sv .cp{color:var(--gr)}.at .cp{color:var(--am)}.no .cp{color:var(--rd)}.em .cp{color:#CBD5E0}
.cs{font-size:11px;color:var(--mu);margin-bottom:.6rem}
.bar{height:4px;background:#EDF2F7;border-radius:3px;margin-bottom:.75rem;overflow:hidden}
.bf{height:4px;border-radius:3px}
.sv .bf{background:var(--gr)}.at .bf{background:var(--am)}.no .bf{background:var(--rd)}.em .bf{background:#CBD5E0}
.cst{display:grid;grid-template-columns:repeat(3,1fr);border-top:1px solid var(--bd);padding-top:.6rem}
.cv{font-size:16px;font-weight:700;text-align:center}
.cl2{font-size:10px;color:var(--mu);text-align:center;margin-top:1px}
.pill{display:inline-flex;align-items:center;gap:4px;font-size:10px;font-weight:600;padding:2px 8px;border-radius:20px;margin-top:.5rem}
.sv .pill{background:var(--gr2);color:var(--gr)}.at .pill{background:var(--am2);color:var(--am)}.no .pill{background:var(--rd2);color:var(--rd)}.em .pill{background:#F7FAFC;color:var(--mu)}
.div{border:none;border-top:1px solid var(--bd);margin:1.5rem 0}
.empty{text-align:center;padding:3rem;color:var(--mu);font-size:13px}
</style>
</head>
<body>
<div class="top">
  <div><h1>Monitor de Inspecoes</h1><p>Zagonel - Qualidade Industrial</p></div>
  <div style="display:flex;align-items:center;gap:12px;">
    <div id="nfo" style="font-size:12px;opacity:.8">Carregando...</div>
    <a href="/logout" style="font-size:11px;color:rgba(255,255,255,.8);text-decoration:none;border:1px solid rgba(255,255,255,.4);padding:4px 10px;border-radius:6px;">Sair</a>
  </div>
</div>
<div class="main">
  <div id="content"><div class="empty">Carregando dados...</div></div>
</div>
<script>
var DB={},SK=["B2-03","B1-01","Injecao"],SN={"B2-03":"Apoio B2-03","B1-01":"Apoio B1-01","Injecao":"Injecao"},SC={"B2-03":"#2563EB","B1-01":"#059669","Injecao":"#7C3AED"};
function fD(k){var d=new Date(k+"T12:00:00");return pad(d.getDate())+"/"+pad(d.getMonth()+1)+"/"+d.getFullYear();}
function pad(n){return n<10?"0"+n:""+n;}
function cl(p,t){if(!t)return"em";if(p<85)return"no";if(p<=100)return"at";return"sv";}
function pt(c){return c==="sv"?"Superou":c==="at"?"Atingiu a meta":c==="no"?"Nao atingiu":"Sem dados";}
function bCard(nome,d){
  var tot=d.total||0,meta=d.meta||0,nc=d.nc||0;
  var pct=meta>0?Math.round(tot/meta*100):0,c=cl(pct,tot);
  var h="<div class=card "+c+"><div class=cn>"+nome+"</div><div class=cm>Meta: "+meta+" inspecoes/dia</div>";
  h+="<div class=cp>"+(!tot?"--":pct+"%")+"</div>";
  h+="<div class=cs>"+(!tot?"Sem registros":tot+" realizadas - meta "+meta)+"</div>";
  h+="<div class=bar><div class=bf style=width:"+(!tot?0:Math.min(pct,100))+"%></div></div>";
  h+="<div class=cst><div><div class=cv>"+tot+"</div><div class=cl2>realizadas</div></div>";
  h+="<div><div class=cv>"+(tot-nc)+"</div><div class=cl2>conformes</div></div>";
  h+="<div><div class=cv>"+meta+"</div><div class=cl2>meta</div></div></div>";
  h+="<span class=pill>"+pt(c)+"</span>";
  if(d.tipos&&Object.keys(d.tipos).length){
    h+="<div style=border-top:1px solid var(--bd);padding-top:.5rem;margin-top:.5rem;font-size:11px;>";
    Object.entries(d.tipos).sort().forEach(function(e){
      var lb=e[0].replace("Inspeção ","").replace("de ","").replace("Diária","").replace("Produção","Início Prod.").trim();
      h+="<div style=display:flex;justify-content:space-between;margin-bottom:2px;><span style=color:var(--mu)>"+lb+"</span><span style=font-weight:600>"+e[1]+"</span></div>";
    });
    h+="</div>";
  }
  h+="</div>";return h;
}
function bSetor(sk,dk){
  var sd=(DB[sk]||{})[dk]||{},col=Object.keys(sd);
  if(!col.length)return"";
  var tot=0,meta=0,nc=0,nsv=0,nat=0,nno=0;
  col.forEach(function(n){var d=sd[n];tot+=d.total;if(d.total>0)meta+=d.meta;nc+=d.nc;var p=d.meta>0?Math.round(d.total/d.meta*100):0,c=cl(p,d.total);if(c==="sv")nsv++;else if(c==="at")nat++;else if(c==="no")nno++;});
  var pct=meta>0?Math.round(tot/meta*100):0;
  var h="<div class=sb><div class=sh><div class=sd style=background:"+SC[sk]+"></div><div class=st>"+SN[sk]+"</div><div class=ss>"+tot+" insp - "+pct+"% meta</div></div>";
  h+="<div class=kg><div class=kc><div class=kl>Inspecoes</div><div class=kv>"+tot+"</div><div class=ks>meta: "+meta+"</div></div>";
  h+="<div class=kc><div class=kl>% da meta</div><div class=kv style=color:"+(pct>=100?"var(--gr)":pct>=85?"var(--am)":"var(--rd);")+">"+pct+"%</div></div>";
  h+="<div class=kc><div class=kl>Status</div><div class=kv style=font-size:12px;line-height:1.8;>";
  if(nsv>0)h+="<span style=color:var(--gr)>"+nsv+" superou</span><br>";
  if(nat>0)h+="<span style=color:var(--am)>"+nat+" atingiu</span><br>";
  if(nno>0)h+="<span style=color:var(--rd)>"+nno+" abaixo</span>";
  h+="</div></div></div><div class=cg>";
  col.forEach(function(n){h+=bCard(n,sd[n],sk,dk);});
  h+="</div></div>";return h;
}
function render(dk){
  var el=document.getElementById("content"),dias=[];
  SK.forEach(function(sk){Object.keys(DB[sk]||{}).forEach(function(d){if(dias.indexOf(d)<0)dias.push(d);});});
  dias.sort(function(a,b){return b.localeCompare(a);});
  if(!dias.length){el.innerHTML="<div class=empty>Nenhum dado disponivel.</div>";return;}
  if(!dk)dk=dias[0];
  var h="<div class=dsel><span class=sl>Data</span><select id=ds onchange=render(this.value)>";
  dias.forEach(function(d){h+="<option value="+d+(d===dk?" selected":"")+">"+fD(d)+"</option>";});
  h+="</select></div>";
  var temDados=false;
  SK.forEach(function(sk){var s=bSetor(sk,dk);if(s){h+=s;h+="<div class=div></div>";temDados=true;}});
  if(!temDados)h+="<div class=empty>Sem dados para esta data.</div>";
  el.innerHTML=h;
}
async function loadDB(){
  try{
    var r=await fetch("/api/data");DB=await r.json();
    var n=Object.values(DB).reduce(function(a,s){return a+Object.keys(s).length;},0);
    document.getElementById("nfo").textContent=n+" dias registrados";
    render();
  }catch(e){document.getElementById("nfo").textContent="Erro ao carregar";}
}
loadDB();
</script>
</body>
</html>'''
