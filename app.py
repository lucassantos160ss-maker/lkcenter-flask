import sqlite3
import os
from datetime import datetime
from flask import Flask, render_template_string, request, redirect, session, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'sua_chave_secreta_super_segura_lk'

DB_PATH = "loja_pecinha.db"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

def salvar_saldo_arquivo(username, saldo, tipo_operacao="ATUALIZACAO"):
    data_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    linha = f"[{data_hora}] Usuario: {username} | Saldo: R$ {saldo:.2f} | Tipo: {tipo_operacao}\n"
    with open("saldos_clientes.txt", "a", encoding="utf-8") as f:
        f.write(linha)

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            saldo REAL DEFAULT 0.00,
            is_admin INTEGER DEFAULT 0,
            codigo_convite TEXT UNIQUE,
            convidado_por INTEGER,
            pontos INTEGER DEFAULT 0,
            nivel_pontos INTEGER DEFAULT 1,
            bonus_pendente_afiliado REAL DEFAULT 0.00
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero_bin TEXT UNIQUE NOT NULL,
            preco_unitario REAL NOT NULL
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS estoque (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bin_id INTEGER,
            conteudo TEXT NOT NULL,
            status TEXT DEFAULT 'disponivel',
            FOREIGN KEY (bin_id) REFERENCES bins (id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS depositos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER,
            valor REAL NOT NULL,
            status TEXT DEFAULT 'pendente',
            data_solicitacao TEXT NOT NULL,
            FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historico_compras (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER,
            detalhes TEXT NOT NULL,
            custo_total REAL NOT NULL,
            data_compra TEXT NOT NULL,
            FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
        )
    """)
    
    cursor.execute("SELECT * FROM usuarios WHERE username = 'S.lucas1'")
    user_lucas = cursor.fetchone()
    if not user_lucas:
        codigo_lucas = "LK777"
        cursor.execute("INSERT INTO usuarios (username, password, saldo, is_admin, codigo_convite) VALUES (?, ?, ?, ?, ?)",
                       ('S.lucas1', generate_password_hash('admin123'), 0.00, 1, codigo_lucas))
    else:
        cursor.execute("UPDATE usuarios SET is_admin = 1, codigo_convite = COALESCE(codigo_convite, 'LK777') WHERE username = 'S.lucas1'")

    bins_iniciais = [
        ("406655", 6.00),
        ("414718", 4.00),
        ("515601", 10.00),
        ("552305", 12.00),
        ("406669", 2.00)
    ]
    for b_num, b_preco in bins_iniciais:
        cursor.execute("INSERT OR IGNORE INTO bins (numero_bin, preco_unitario) VALUES (?, ?)", (b_num, b_preco))
        
    conn.commit()
    conn.close()

DASHBOARD_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Plus Jakarta Sans', sans-serif; letter-spacing: 0.3px; }
    
    @keyframes gradientBG {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }

    body {
        background: linear-gradient(-45deg, #050505, #121214, #1a1a1e, #0a0a0c, #2a2a30);
        background-size: 400% 400%;
        animation: gradientBG 12s ease infinite;
        color: #e2e8f0;
        min-height: 100vh;
        padding: 25px;
        display: flex;
        justify-content: center;
        -webkit-text-size-adjust: 100%;
    }

    .wrapper { width: 100%; max-width: 1150px; }
    .topbar {
        display: flex; justify-content: space-between; align-items: center;
        background: rgba(18, 18, 22, 0.85); backdrop-filter: blur(16px);
        padding: 16px 24px; border-radius: 18px; border: 1px solid rgba(255, 255, 255, 0.15);
        box-shadow: 0 10px 30px rgba(0,0,0,0.8); margin-bottom: 25px;
        flex-wrap: wrap; gap: 15px;
    }
    .brand { display: flex; align-items: center; gap: 14px; }
    .brand-img { width: 52px; height: 52px; border-radius: 50%; object-fit: cover; border: 2px solid #e2e8f0; }
    .brand-title {
        background: linear-gradient(135deg, #ffffff, #a1a1aa, #d4d4d8);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        font-size: 1.4rem; font-weight: 800; letter-spacing: 0.5px; text-transform: uppercase;
    }
    .nav-actions { display: flex; gap: 12px; margin-top: 6px; flex-wrap: wrap; }
    .btn-action {
        background: linear-gradient(135deg, #22c55e, #16a34a); color: #ffffff;
        font-weight: 700; border: none; padding: 10px 20px; border-radius: 10px;
        cursor: pointer; text-decoration: none; font-size: 0.88rem; transition: all 0.2s ease;
        display: inline-block; text-align: center;
    }
    .btn-action:hover { transform: translateY(-2px); filter: brightness(1.15); }
    .btn-silver { background: linear-gradient(135deg, #52525b, #27272a); color: #fff; border: 1px solid rgba(255, 255, 255, 0.2); }
    .btn-danger { background: linear-gradient(135deg, #ef4444, #dc2626); color: #fff; }

    .user-pill {
        background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.15);
        padding: 8px 18px; border-radius: 30px; display: flex; align-items: center; gap: 12px;
    }
    .user-avatar {
        width: 34px; height: 34px; background: #3f3f46; border: 1px solid #a1a1aa;
        border-radius: 50%; display: flex; align-items: center; justify-content: center;
        font-size: 0.85rem; color: #fff; font-weight: 800; text-transform: uppercase;
    }
    .user-name { color: #f8fafc; font-size: 0.85rem; font-weight: 700; }
    .user-balance { color: #4ade80; font-size: 0.92rem; font-weight: 800; }

    .metrics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 20px; margin-bottom: 25px; }
    .metric-card {
        background: rgba(24, 24, 27, 0.85); border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 16px; padding: 20px; display: flex; align-items: center; gap: 18px;
    }
    .metric-icon { width: 48px; height: 48px; border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 1.3rem; }
    .icon-silver { background: rgba(255, 255, 255, 0.1); color: #f4f4f5; }
    .icon-green { background: rgba(34, 197, 94, 0.15); color: #4ade80; }
    .metric-val { color: #ffffff; font-size: 1.6rem; font-weight: 800; }
    .metric-lbl { color: #a1a1aa; font-size: 0.75rem; font-weight: 700; text-transform: uppercase; margin-top: 5px; }

    .main-grid { display: grid; grid-template-columns: 1.8fr 1.2fr; gap: 25px; }
    @media(max-width: 850px) { .main-grid { grid-template-columns: 1fr; } body { padding: 12px; } }

    .panel-box {
        background: rgba(18, 18, 22, 0.9); border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 18px; padding: 25px; backdrop-filter: blur(12px); margin-bottom: 25px;
    }
    .panel-header { display: flex; align-items: center; gap: 10px; margin-bottom: 20px; border-bottom: 1px solid rgba(255, 255, 255, 0.08); padding-bottom: 14px; }
    .panel-title { color: #ffffff; font-size: 1.1rem; font-weight: 800; }

    label { display: block; font-size: 0.78rem; color: #a1a1aa; margin-bottom: 8px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; }
    select, input, textarea {
        width: 100%; background: rgba(9, 9, 11, 0.8); border: 1px solid rgba(255, 255, 255, 0.18);
        border-radius: 12px; padding: 14px; color: #f8fafc; font-size: 0.95rem; font-weight: 600; margin-bottom: 18px;
    }

    .btn-buy-action {
        width: 100%; background: linear-gradient(135deg, #e2e8f0, #94a3b8);
        color: #09090b; font-weight: 800; padding: 16px; border: none;
        border-radius: 12px; font-size: 1rem; cursor: pointer; transition: all 0.2s;
    }

    .output-area {
        background: #000000; border: 1px solid rgba(34, 197, 94, 0.3);
        border-radius: 12px; padding: 16px; height: 180px; overflow-y: auto;
        font-family: monospace; font-size: 0.9rem; color: #4ade80;
    }

    .grid-bins { display: grid; grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); gap: 12px; max-height: 320px; overflow-y: auto; }
    .bin-badge {
        background: rgba(39, 39, 42, 0.9); border: 1px solid rgba(255, 255, 255, 0.15);
        color: #ffffff; padding: 14px 10px; border-radius: 12px; text-align: center; font-weight: 800;
    }

    .modal-overlay {
        display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%;
        background: rgba(0,0,0,0.85); backdrop-filter: blur(8px);
        z-index: 999; justify-content: center; align-items: center;
    }
    .modal-card {
        background: #18181b; border: 1px solid rgba(255, 255, 255, 0.2);
        padding: 30px; border-radius: 20px; width: 90%; max-width: 450px; text-align: center;
    }
    
    table { width: 100%; border-collapse: collapse; margin-top: 10px; }
    th, td { padding: 12px; text-align: left; border-bottom: 1px solid rgba(255,255,255,0.1); font-size: 0.9rem; }
    th { color: #a1a1aa; font-weight: 700; text-transform: uppercase; }

    #toast-container {
        position: fixed; bottom: 20px; right: 20px; z-index: 9999;
        display: flex; flex-direction: column; gap: 10px; max-width: 320px; width: 100%;
    }
    .toast-notification {
        background: rgba(24, 24, 27, 0.95); border: 1px solid rgba(34, 197, 94, 0.4);
        border-left: 4px solid #22c55e; border-radius: 12px; padding: 12px 16px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.5); backdrop-filter: blur(8px);
        animation: slideInRight 0.3s ease, fadeOut 0.5s ease 4.5s forwards;
        display: flex; align-items: center; gap: 12px;
    }
    @keyframes slideInRight {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    @keyframes fadeOut {
        to { opacity: 0; transform: translateY(10px); }
    }
    .toast-icon { font-size: 1.4rem; }
    .toast-text { font-size: 0.82rem; color: #f8fafc; font-weight: 600; line-height: 1.3; }
    .toast-text span { color: #4ade80; font-weight: 700; }

    #install-banner {
        display: none; background: linear-gradient(135deg, rgba(34,197,94,0.15), rgba(18,18,22,0.95));
        border: 1px solid rgba(34,197,94,0.3); border-radius: 14px; padding: 14px 20px;
        margin-bottom: 25px; align-items: center; justify-content: space-between; gap: 15px;
    }
</style>
"""

AUTH_HTML = DASHBOARD_CSS + """
<div style="width:100%; max-width:400px; margin: 60px auto;">
    <div class="panel-box">
        <div style="text-align:center; margin-bottom:20px;">
            <img src="/static/pecinha_logo.jpg" alt="PECINHA" style="width:70px; height:70px; border-radius:50%; border:2px solid #fff;">
            <h2 style="color:#fff; margin-top:10px;">CENTER DO PECINHA</h2>
        </div>
        <form method="POST">
            <label>Usuário</label>
            <input type="text" name="username" required>
            <label>Senha</label>
            <input type="password" name="password" required>
            <button type="submit" class="btn-action" style="width:100%;">Entrar</button>
        </form>
    </div>
</div>
"""

@app.route('/')
def index():
    return "Loja funcionando com sucesso!"

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
