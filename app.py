import os, json, base64, requests
from flask import Flask, request, jsonify, Response
from datetime import datetime
import pandas as pd
from io import BytesIO

app = Flask(__name__)

DATA_FILE    = os.environ.get('DATA_FILE', '/data/data.json')
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
