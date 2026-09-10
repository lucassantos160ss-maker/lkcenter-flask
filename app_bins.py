import sqlite3
import os
from datetime import datetime, timedelta
from flask import Flask, render_template_string, request, redirect, session, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'sua_chave_secreta_super_segura_lk'

DB_PATH = "loja_pecinha.db"
PASTA_ESTOQUE = "saldos e estoques"

# Garante que a pasta de saldos e estoques existe
if not os.path.exists(PASTA_ESTOQUE):
    os.makedirs(PASTA_ESTOQUE)

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    return conn

def salvar_saldo_arquivo(username, saldo, tipo_operacao="ATUALIZACAO"):
    try:
        data_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        linha = f"[{data_hora}] Usuario: {username} | Saldo: R$ {saldo:.2f} | Tipo: {tipo_operacao}\n"
        caminho_arquivo = os.path.join(PASTA_ESTOQUE, "saldo.txt")
        with open(caminho_arquivo, "a", encoding="utf-8") as f:
            f.write(linha)
    except Exception as e:
        print(f"Erro ao salvar saldo em arquivo: {e}")

def atualizar_arquivo_estoque_geral():
    try:
        conn = get_db_connection()
        estoques = conn.execute("""
            SELECT e.id, b.numero_bin, e.conteudo, e.status 
            FROM estoque e 
            JOIN bins b ON b.id = e.bin_id
        """).fetchall()
        conn.close()
        
        caminho_arquivo = os.path.join(PASTA_ESTOQUE, "estoque.txt")
        with open(caminho_arquivo, "w", encoding="utf-8") as f:
            for item in estoques:
                f.write(f"BIN: {item['numero_bin']} | Status: {item['status']} | Conteudo: {item['conteudo']}\n")
    except Exception as e:
        print(f"Erro ao atualizar arquivo estoque.txt: {e}")

def registrar_historico_compra(usuario_id, bin_numero, quantidade, custo_total, itens_comprados):
    try:
        data_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = get_db_connection()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS historico_compras (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER,
                bin_numero TEXT,
                quantidade INTEGER,
                custo_total REAL,
                itens TEXT,
                data_hora TEXT,
                FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
            )
        """)
        itens_str = ", ".join(itens_comprados)
        conn.execute("""
            INSERT INTO historico_compras (usuario_id, bin_numero, quantidade, custo_total, itens, data_hora)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (usuario_id, bin_numero, quantidade, custo_total, itens_str, data_hora))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Erro ao registrar histórico de compras: {e}")

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
            indicado_por TEXT DEFAULT NULL
        )
    """)
    
    try:
        cursor.execute("ALTER TABLE usuarios ADD COLUMN indicado_por TEXT DEFAULT NULL")
    except Exception:
        pass
    
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
            bin_numero TEXT,
            quantidade INTEGER,
            custo_total REAL,
            itens TEXT,
            data_hora TEXT,
            FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
        )
    """)
    
    cursor.execute("SELECT * FROM usuarios WHERE username = 'S.lucas1'")
    user_lucas = cursor.fetchone()
    if not user_lucas:
        cursor.execute("INSERT INTO usuarios (username, password, saldo, is_admin) VALUES (?, ?, ?, ?)",
                       ('S.lucas1', generate_password_hash('admin123'), 0.00, 1))
    else:
        cursor.execute("UPDATE usuarios SET is_admin = 1 WHERE username = 'S.lucas1'")

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
    atualizar_arquivo_estoque_geral()

DASHBOARD_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Plus Jakarta Sans', sans-serif; }
    
    @keyframes darkSilverFlow {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }

    @keyframes fadeInScale {
        from { opacity: 0; transform: scale(0.96) translateY(10px); }
        to { opacity: 1; transform: scale(1) translateY(0); }
    }

    body {
        background: linear-gradient(-45deg, #050505, #121212, #1c1c1c, #0a0a0a, #000000);
        background-size: 400% 400%;
        animation: darkSilverFlow 14s ease infinite;
        color: #e5e7eb;
        min-height: 100vh;
        padding: 15px;
        display: flex;
        justify-content: center;
        opacity: 0;
        animation: darkSilverFlow 14s ease infinite, fadeInScale 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards;
    }

    .wrapper { width: 100%; max-width: 1150px; animation: fadeInScale 0.5s ease-out; }
    
    .topbar {
        display: flex; justify-content: space-between; align-items: center;
        background: rgba(18, 18, 18, 0.85); backdrop-filter: blur(16px);
        padding: 14px 18px; border-radius: 18px; border: 1px solid rgba(255, 255, 255, 0.08);
        box-shadow: 0 10px 30px rgba(0,0,0,0.8); margin-bottom: 20px;
        flex-wrap: wrap; gap: 12px;
    }
    
    .brand { display: flex; align-items: center; gap: 12px; }
    .brand-img { 
        width: 44px; height: 44px; border-radius: 50%; object-fit: cover; 
        border: 2px solid #a3a3a3; box-shadow: 0 0 15px rgba(255, 255, 255, 0.15); 
        transition: transform 0.3s ease;
    }
    .brand-img:hover { transform: scale(1.08) rotate(3deg); }
    
    .brand-title {
        background: linear-gradient(135deg, #ffffff, #d4d4d4, #737373);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        font-size: 1.15rem; font-weight: 800; letter-spacing: -0.5px; text-transform: uppercase;
    }
    
    .nav-actions { display: flex; gap: 8px; margin-top: 4px; flex-wrap: wrap; }
    .btn-action {
        background: linear-gradient(135deg, #262626, #171717); color: #f5f5f5;
        font-weight: 700; border: 1px solid rgba(255, 255, 255, 0.15); padding: 8px 14px; border-radius: 10px;
        cursor: pointer; text-decoration: none; font-size: 0.8rem; 
        transition: all 0.25s ease;
        display: inline-block; text-align: center; box-shadow: 0 4px 12px rgba(0,0,0,0.5);
    }
    .btn-action:hover { transform: translateY(-2px); background: linear-gradient(135deg, #404040, #262626); border-color: rgba(255, 255, 255, 0.3); }

    .btn-silver { background: linear-gradient(135deg, #262626, #0f0f0f); color: #e5e7eb; border: 1px solid rgba(255, 255, 255, 0.1); }
    .btn-danger { background: linear-gradient(135deg, #7f1d1d, #450a0a); color: #fca5a5; border: 1px solid rgba(239, 68, 68, 0.3); }
    .btn-danger:hover { background: linear-gradient(135deg, #991b1b, #7f1d1d); }

    .user-pill {
        background: rgba(10, 10, 10, 0.8); border: 1px solid rgba(255, 255, 255, 0.1);
        padding: 6px 14px; border-radius: 30px; display: flex; align-items: center; gap: 10px;
    }
    .user-avatar {
        width: 30px; height: 30px; background: #262626; border: 1px solid #737373;
        border-radius: 50%; display: flex; align-items: center; justify-content: center;
        font-size: 0.75rem; color: #fff; font-weight: 800; text-transform: uppercase;
    }
    .user-name { color: #f3f4f6; font-size: 0.8rem; font-weight: 700; }
    .user-balance { color: #d4d4d4; font-size: 0.85rem; font-weight: 800; }

    .metrics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 15px; margin-bottom: 20px; }
    .metric-card {
        background: linear-gradient(135deg, rgba(20, 20, 20, 0.9), rgba(10, 10, 10, 0.9)); 
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 16px; padding: 16px; display: flex; align-items: center; gap: 14px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.6);
    }
    .metric-icon { width: 40px; height: 40px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 1.1rem; flex-shrink: 0; }
    .icon-silver { background: linear-gradient(135deg, #383838, #1a1a1a); color: #f5f5f5; border: 1px solid rgba(255,255,255,0.15); }
    .metric-val { color: #ffffff; font-size: 1.3rem; font-weight: 800; }
    .metric-lbl { color: #a3a3a3; font-size: 0.68rem; font-weight: 700; text-transform: uppercase; margin-top: 3px; }

    .main-grid { display: grid; grid-template-columns: 1.6fr 1.1fr; gap: 20px; }
    @media(max-width: 900px) { .main-grid { grid-template-columns: 1fr; } }

    .panel-box {
        background: linear-gradient(145deg, rgba(18, 18, 18, 0.85), rgba(8, 8, 8, 0.9)); 
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 18px; padding: 18px; margin-bottom: 20px;
        box-shadow: 0 15px 35px rgba(0,0,0,0.7);
    }
    .panel-header { display: flex; align-items: center; gap: 8px; margin-bottom: 16px; border-bottom: 1px solid rgba(255, 255, 255, 0.08); padding-bottom: 10px; }
    .panel-title { color: #ffffff; font-size: 1rem; font-weight: 800; }

    label { display: block; font-size: 0.72rem; color: #a3a3a3; margin-bottom: 6px; font-weight: 700; text-transform: uppercase; }
    select, input, textarea {
        width: 100%; background: rgba(5, 5, 5, 0.9); border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 12px; padding: 12px; color: #f3f4f6; font-size: 0.9rem; font-weight: 600; margin-bottom: 15px;
    }
    select:focus, input:focus, textarea:focus { border-color: #d4d4d4; outline: none; }

    .btn-buy-action {
        width: 100%; background: linear-gradient(135deg, #e5e5e5, #737373);
        color: #000000; font-weight: 800; padding: 14px; border: none;
        border-radius: 12px; font-size: 0.95rem; cursor: pointer; 
        box-shadow: 0 4px 20px rgba(255, 255, 255, 0.2);
    }
    .btn-buy-action:hover { filter: brightness(1.15); }

    .output-area {
        background: #030303; border: 1px solid rgba(255, 255, 255, 0.15);
        border-radius: 12px; padding: 14px; height: 160px; overflow-y: auto;
        font-family: monospace; font-size: 0.85rem; color: #e5e7eb;
    }

    .grid-bins { display: grid; grid-template-columns: repeat(auto-fill, minmax(110px, 1fr)); gap: 10px; max-height: 280px; overflow-y: auto; }
    .bin-badge {
        background: linear-gradient(135deg, rgba(26, 26, 26, 0.9), rgba(10, 10, 10, 0.9)); 
        border: 1px solid rgba(255, 255, 255, 0.15);
        color: #ffffff; padding: 12px 8px; border-radius: 12px; text-align: center; font-weight: 800;
        font-size: 0.85rem;
    }

    .modal-overlay {
        display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%;
        background: rgba(0,0,0,0.85); backdrop-filter: blur(8px);
        z-index: 999; justify-content: center; align-items: center; padding: 15px;
    }
    .modal-overlay.active { display: flex; }
    
    .modal-card {
        background: linear-gradient(145deg, #121212, #080808); 
        border: 1px solid rgba(255, 255, 255, 0.2);
        padding: 24px; border-radius: 20px; width: 100%; max-width: 440px; text-align: center;
        max-height: 90vh; overflow-y: auto;
    }
    
    table { width: 100%; border-collapse: collapse; margin-top: 10px; }
    th, td { padding: 10px 8px; text-align: left; border-bottom: 1px solid rgba(255,255,255,0.06); font-size: 0.82rem; }
    th { color: #a3a3a3; font-weight: 700; text-transform: uppercase; }
    
    .table-responsive { width: 100%; overflow-x: auto; }

    #toast-container {
        position: fixed; bottom: 20px; right: 20px; z-index: 9999;
        display: flex; flex-direction: column; gap: 10px; pointer-events: none;
    }
    .toast {
        background: rgba(18, 18, 18, 0.95); border: 1px solid rgba(255, 255, 255, 0.2);
        color: #fff; padding: 12px 18px; border-radius: 12px; font-size: 0.85rem; font-weight: 700;
        box-shadow: 0 10px 30px rgba(0,0,0,0.8); pointer-events: auto;
        display: flex; align-items: center; gap: 10px;
    }
</style>

<script>
    function showToast(message, isSuccess = true) {
        let container = document.getElementById('toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            document.body.appendChild(container);
        }
        const toast = document.createElement('div');
        toast.className = 'toast';
        toast.style.borderColor = isSuccess ? '#34d399' : '#ef4444';
        toast.innerHTML = `<span>${isSuccess ? '✅' : '⚠️'}</span> ${message}`;
        container.appendChild(toast);

        setTimeout(() => {
            toast.remove();
        }, 3500);
    }

    function openModal() { 
        const modal = document.getElementById('pixModal');
        modal.classList.add('active');
    }
    
    function closeModal() { 
        const modal = document.getElementById('pixModal');
        modal.classList.remove('active');
    }

    function copiarPix() {
        var copyText = document.getElementById("chavePixInput");
        copyText.select();
        navigator.clipboard.writeText(copyText.value).then(() => {
            showToast("Chave PIX copiada com sucesso!", true);
        });
    }

    function copiarAfiliado() {
        var copyText = document.getElementById("linkAfiliadoInput");
        copyText.select();
        navigator.clipboard.writeText(copyText.value).then(() => {
            showToast("Link de afiliado copiado com sucesso!", true);
        });
    }

    function filtrarBins() {
        let input = document.getElementById('buscaBin').value.toLowerCase();
        let badges = document.getElementsByClassName('bin-badge');
        for (let i = 0; i < badges.length; i++) {
            let texto = badges[i].innerText.toLowerCase();
            if (texto.includes(input)) {
                badges[i].style.display = "";
            } else {
                badges[i].style.display = "none";
            }
        }
    }

    function tocarSomSucessoPlim() {
        try {
            const AudioContext = window.AudioContext || window.webkitAudioContext;
            if (!AudioContext) return;
            const ctx = new AudioContext();
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            
            osc.type = 'sine';
            osc.frequency.setValueAtTime(880, ctx.currentTime);
            osc.frequency.exponentialRampToValueAtTime(1760, ctx.currentTime + 0.15);
            
            gain.gain.setValueAtTime(0.3, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.6);
            
            osc.connect(gain);
            gain.connect(ctx.destination);
            
            osc.start();
            osc.stop(ctx.currentTime + 0.6);
        } catch(err) {
            console.log("Erro ao tocar áudio nativo:", err);
        }
    }
</script>
"""

AUTH_HTML = DASHBOARD_CSS + """
<div style="width:100%; max-width:380px; margin: auto; display: flex; align-items: center; min-height: 100vh;">
    <div class="panel-box" style="width: 100%;">
        <div style="text-align:center; margin-bottom:20px;">
            <img src="/static/pecinha_logo.jpg" alt="PECINHA" style="width:64px; height:64px; border-radius:50%; border:2px solid #a3a3a3;">
            <h2 style="color:#fff; margin-top:10px; font-weight:800; font-size: 1.2rem;">CENTER DO PECINHA</h2>
            {% if indicado_por %}
                <p style="color:#34d399; font-size:0.75rem; margin-top:6px; font-weight:700;">🎁 Você foi indicado por: {{ indicado_por }}</p>
            {% endif %}
        </div>

        {% if error %}
            <div style="background: rgba(127, 29, 29, 0.3); border: 1px solid #ef4444; color: #fca5a5; padding: 10px; border-radius: 8px; margin-bottom: 15px; font-size: 0.8rem;">
                {{ error }}
            </div>
        {% endif %}

        <form method="POST" action="{{ action }}">
            {% if indicado_por %}
                <input type="hidden" name="indicado_por" value="{{ indicado_por }}">
            {% endif %}
            <label>Usuário</label>
            <input type="text" name="username" placeholder="Digite seu usuário" required>
            
            <label>Senha</label>
            <input type="password" name="password" placeholder="Digite sua senha" required>

            <button type="submit" class="btn-buy-action" style="margin-top:5px;">{{ title }}</button>
        </form>

        <div style="text-align:center; margin-top:18px;">
            {% if title == 'Login' %}
                <p style="font-size:0.8rem; color:#a3a3a3;">Não tem uma conta? <a href="/register{% if indicado_por %}?ref={{ indicado_por }}{% endif %}" style="color:#f3f4f6; font-weight:700; text-decoration:underline;">Cadastre-se</a></p>
            {% else %}
                <p style="font-size:0.8rem; color:#a3a3a3;">Já possui conta? <a href="/login{% if indicado_por %}?ref={{ indicado_por }}{% endif %}" style="color:#f3f4f6; font-weight:700; text-decoration:underline;">Entrar</a></p>
            {% endif %}
        </div>
    </div>
</div>
"""

INDEX_HTML = DASHBOARD_CSS + """
<div class="wrapper">
    {% if entregues %}
    <script>
        window.addEventListener('DOMContentLoaded', () => {
            tocarSomSucessoPlim();
            showToast("Compra realizada com sucesso!", true);
        });
    </script>
    {% endif %}

    <div class="topbar">
        <div>
            <div class="brand">
                <img src="/static/pecinha_logo.jpg" alt="PECINHA" class="brand-img">
                <div class="brand-title">CENTER DO PECINHA</div>
            </div>
            <div class="nav-actions">
                <a href="/" class="btn-action btn-silver">Comprar BINs</a>
                <button onclick="openModal()" class="btn-action">+ Adicionar Saldo</button>
                {% if usuario.username == 'S.lucas1' %}
                    <a href="/admin_secret_lk" class="btn-action btn-silver">Painel Admin</a>
                {% endif %}
                <a href="/logout" class="btn-action btn-danger">Sair</a>
            </div>
        </div>

        <div class="user-pill">
            <div class="user-avatar">{{ usuario.username[:2] }}</div>
            <div>
                <div class="user-name">{{ usuario.username }}</div>
                <div class="user-balance">R$ {{ "%.2f"|format(usuario.saldo) }}</div>
            </div>
        </div>
    </div>

    <div class="metrics-grid">
        <div class="metric-card">
            <div class="metric-icon icon-silver">💳</div>
            <div>
                <div class="metric-val">{{ total_bins }}</div>
                <div class="metric-lbl">BINs DISPONÍVEIS</div>
            </div>
        </div>
        <div class="metric-card">
            <div class="metric-icon icon-silver">📦</div>
            <div>
                <div class="metric-val">{{ estoque_total }}</div>
                <div class="metric-lbl">ESTOQUE TOTAL</div>
            </div>
        </div>
    </div>

    <div class="main-grid">
        <div class="panel-box">
            <div class="panel-header">
                <span style="color:#f3f4f6;">💳</span>
                <span class="panel-title">Comprar BINs</span>
            </div>

            {% if erro %}
                <script>
                    window.addEventListener('DOMContentLoaded', () => {
                        showToast("{{ erro }}", false);
                    });
                </script>
                <div style="background: rgba(127, 29, 29, 0.3); border: 1px solid #ef4444; color: #fca5a5; padding: 10px; border-radius: 10px; margin-bottom: 15px; font-size: 0.8rem; font-weight:600;">
                    ⚠️ {{ erro }}
                </div>
            {% endif %}

            {% if lista_bins %}
            <form action="/comprar" method="POST">
                <label>SELECIONE A BIN</label>
                <select name="bin_id" required>
                    {% for b in lista_bins %}
                        <option value="{{ b.id }}">BIN: {{ b.numero_bin }} — R$ {{ "%.2f"|format(b.preco) }} (Disp: {{ b.estoque }})</option>
                    {% endfor %}
                </select>

                <label>QUANTIDADE DESEJADA</label>
                <input type="number" min="1" max="50" name="quantidade" value="1" required>

                <button type="submit" class="btn-buy-action">Comprar BINs</button>
            </form>
            {% else %}
                <p style="color:#a3a3a3; font-size:0.85rem; font-weight:600;">Nenhuma BIN com estoque disponível no momento.</p>
            {% endif %}

            {% if entregues %}
                <div style="margin-top: 18px;">
                    <label style="color:#e5e7eb;">✅ ITENS ENTREGUES COM SUCESSO</label>
                    <div class="output-area">
                        {% for item in entregues %}
                            {{ item }}<br>
                        {% endfor %}
                    </div>
                </div>
            {% endif %}
        </div>

        <div class="panel-box">
            <div class="panel-header">
                <span style="color:#f3f4f6;">🏷️</span>
                <span class="panel-title">Catálogo de BINs</span>
            </div>
            
            <input type="text" id="buscaBin" onkeyup="filtrarBins()" placeholder="🔍 Buscar BIN..." style="margin-bottom: 12px; font-size: 0.8rem; padding: 10px;">

            <div class="grid-bins">
                {% if lista_bins %}
                    {% for b in lista_bins %}
                        <div class="bin-badge">
                            {{ b.numero_bin }}<br>
                            <span style="color:#a3a3a3; font-size:0.78rem;">R$ {{ "%.2f"|format(b.preco) }}</span>
                        </div>
                    {% endfor %}
                {% else %}
                    <p style="color:#a3a3a3; font-size:0.8rem; grid-column: 1/-1;">Sem BINs disponíveis.</p>
                {% endif %}
            </div>
        </div>
    </div>
</div>

<div id="pixModal" class="modal-overlay">
    <div class="modal-card">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
            <h3 style="color:#fff; font-size: 1.1rem;">Adicionar Saldo (Pix)</h3>
            <button type="button" onclick="closeModal()" style="background:transparent; border:none; color:#a3a3a3; font-size:1.2rem; cursor:pointer; font-weight:bold;">&times;</button>
        </div>
        <p style="color:#a3a3a3; font-size:0.8rem; margin-bottom:14px;">Recarga mínima: <strong>R$ 10,00</strong>. Copie a chave abaixo:</p>
        
        <label>Chave Pix Aleatória</label>
        <div style="display:flex; gap:6px; margin-bottom:14px;">
            <input type="text" id="chavePixInput" value="dc18f929-8808-4baa-a540-9d89036da62c" readonly style="margin-bottom:0; font-size:0.75rem;">
            <button onclick="copiarPix()" class="btn-action" style="padding:10px; flex-shrink: 0;">Copiar</button>
        </div>

        <form action="/depositar" method="POST" style="margin-bottom: 14px;">
            <label>Informe o valor pago no Pix</label>
            <input type="number" step="0.01" min="10" name="valor" placeholder="10.00" required>
            <p style="color:#d4d4d4; font-size:0.7rem; margin-bottom:14px;">O saldo será creditado após a aprovação do suporte.</p>
            <button type="submit" class="btn-action" style="width:100%; margin-bottom:8px;">Confirmar Depósito</button>
        </form>

        <div style="border-top: 1px solid rgba(255,255,255,0.1); padding-top: 12px; text-align: left;">
            <label style="color:#34d399; font-weight:800; font-size:0.75rem;">🚀 PROGRAMA DE AFILIADOS / INDICAÇÃO</label>
            <p style="color:#a3a3a3; font-size:0.72rem; margin-bottom:8px; line-height: 1.3;">
                Compartilhe seu link exclusivo abaixo. Quem se cadastrar por ele ganha <strong>R$ 15,00 de bônus</strong> no primeiro depósito, e você recebe <strong>R$ 10,00</strong> de comissão!
            </p>
            <div style="display:flex; gap:6px;">
                <input type="text" id="linkAfiliadoInput" value="{{ link_afiliado }}" readonly style="margin-bottom:0; font-size:0.72rem;">
                <button onclick="copiarAfiliado()" class="btn-action" style="padding:8px 10px; flex-shrink: 0; font-size:0.75rem;">Copiar Link</button>
            </div>
        </div>

        <div style="margin-top: 12px;">
            <button type="button" onclick="closeModal()" style="background:transparent; border:none; color:#a3a3a3; cursor:pointer; font-size: 0.8rem; font-weight:700;">Fechar / Sair</button>
        </div>
    </div>
</div>
"""

ADMIN_HTML = DASHBOARD_CSS + """
<div class="wrapper">
    <div class="topbar">
        <div class="brand">
            <img src="/static/pecinha_logo.jpg" alt="PECINHA" class="brand-img">
            <div class="brand-title">Painel Admin</div>
        </div>
        <a href="/" class="btn-action btn-silver">← Voltar para a Loja</a>
    </div>

    {% if mensagem %}
        <script>
            window.addEventListener('DOMContentLoaded', () => {
                showToast("{{ mensagem }}", true);
            });
        </script>
        <div style="background: rgba(38, 38, 38, 0.9); border: 1px solid #737373; color: #f5f5f5; padding: 10px; border-radius: 10px; margin-bottom: 15px; font-size: 0.8rem; font-weight:600;">
            ✅ {{ mensagem }}
        </div>
    {% endif %}

    <div class="metrics-grid">
        <div class="metric-card">
            <div class="metric-icon icon-silver">👥</div>
            <div>
                <div class="metric-val">{{ total_usuarios }}</div>
                <div class="metric-lbl">TOTAL DE USUÁRIOS</div>
            </div>
        </div>
        <div class="metric-card">
            <div class="metric-icon icon-silver">⏳</div>
            <div>
                <div class="metric-val">{{ total_depositos_pendentes }}</div>
                <div class="metric-lbl">DEPÓSITOS PENDENTES</div>
            </div>
        </div>
    </div>

    <div class="panel-box">
        <div class="panel-title" style="margin-bottom:12px; color:#f8fafc;">📋 Histórico de Compras & GGs Entregues</div>
        
        <!-- Formulário de Filtro de Histórico -->
        <form method="GET" action="/admin_secret_lk" style="display: flex; gap: 10px; align-items: center; margin-bottom: 15px; flex-wrap: wrap;">
            <div style="flex: 1; min-width: 200px;">
                <label style="margin-bottom: 4px;">Filtrar por Usuário</label>
                <input type="text" name="filtro_usuario" value="{{ filtro_usuario or '' }}" placeholder="Nome do usuário..." style="margin-bottom: 0; padding: 8px; font-size: 0.8rem;">
            </div>
            <div style="flex: 1; min-width: 150px;">
                <label style="margin-bottom: 4px;">Data Inicial</label>
                <input type="date" name="filtro_data_inicio" value="{{ filtro_data_inicio or '' }}" style="margin-bottom: 0; padding: 8px; font-size: 0.8rem;">
            </div>
            <div style="flex: 1; min-width: 150px;">
                <label style="margin-bottom: 4px;">Data Final</label>
                <input type="date" name="filtro_data_fim" value="{{ filtro_data_fim or '' }}" style="margin-bottom: 0; padding: 8px; font-size: 0.8rem;">
            </div>
            <div style="display: flex; gap: 6px; align-self: flex-end;">
                <button type="submit" class="btn-action" style="padding: 10px 14px; font-size: 0.78rem;">Filtrar</button>
                <a href="/admin_secret_lk" class="btn-action btn-silver" style="padding: 10px 14px; font-size: 0.78rem; display: flex; align-items: center; text-decoration: none;">Limpar</a>
            </div>
        </form>

        {% if historico_compras %}
            <div class="table-responsive">
                <table>
                    <thead>
                        <tr>
                            <th>Data/Hora</th>
                            <th>Usuário</th>
                            <th>BIN</th>
                            <th>Qtd</th>
                            <th>Total</th>
                            <th>Itens (GGs)</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for h in historico_compras %}
                        <tr>
                            <td style="font-size:0.75rem; color:#a3a3a3;">{{ h.data_hora }}</td>
                            <td><strong>{{ h.username }}</strong></td>
                            <td>{{ h.bin_numero }}</td>
                            <td>{{ h.quantidade }}</td>
                            <td style="color:#d4d4d4;">R$ {{ "%.2f"|format(h.custo_total) }}</td>
                            <td style="font-family:monospace; font-size:0.75rem; color:#e5e7eb; word-break:break-all;">{{ h.itens }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        {% else %}
            <p style="color:#a3a3a3; font-size:0.8rem;">Nenhum registro encontrado com os filtros atuais.</p>
        {% endif %}
    </div>

    <div class="panel-box">
        <div class="panel-title" style="margin-bottom:12px; color:#f8fafc;">📥 Depósitos Pix Pendentes</div>
        {% if depositos %}
            <div class="table-responsive">
                <table>
                    <thead>
                        <tr>
                            <th>Usuário</th>
                            <th>Valor</th>
                            <th>Data</th>
                            <th>Ação</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for d in depositos %}
                        <tr>
                            <td><strong>{{ d.username }}</strong></td>
                            <td style="color:#d4d4d4;">R$ {{ "%.2f"|format(d.valor) }}</td>
                            <td style="font-size:0.75rem;">{{ d.data_solicitacao }}</td>
                            <td>
                                <a href="/admin/deposito/aprovar/{{ d.id }}" class="btn-action" style="padding:5px 10px; font-size:0.7rem;">Aprovar</a>
                                <a href="/admin/deposito/rejeitar/{{ d.id }}" class="btn-action btn-danger" style="padding:5px 10px; font-size:0.7rem;">Rejeitar</a>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        {% else %}
            <p style="color:#a3a3a3; font-size:0.8rem;">Nenhum depósito pendente no momento.</p>
        {% endif %}
    </div>

    <div class="panel-box">
        <div class="panel-title" style="margin-bottom:12px; color:#f8fafc;">💰 Adicionar Saldo Manual a Usuário</div>
        <form action="/admin/usuario/saldo" method="POST">
            <label>USUÁRIO</label>
            <select name="usuario_id" required>
                {% for u in usuarios %}
                    <option value="{{ u.id }}">{{ u.username }} (Saldo: R$ {{ "%.2f"|format(u.saldo) }})</option>
                {% endfor %}
            </select>
            <label>VALOR A ADICIONAR (R$)</label>
            <input type="number" step="0.01" name="valor" placeholder="Ex: 50.00" required>
            <button type="submit" class="btn-buy-action">Injetar Saldo</button>
        </form>
    </div>

    <div class="main-grid" style="margin-bottom:20px;">
        <div class="panel-box">
            <div class="panel-title" style="margin-bottom:12px; color:#f8fafc;">✏️ Alterar Valor da BIN</div>
            <form action="/admin/bin/editar" method="POST">
                <label>SELECIONE A BIN</label>
                <select name="bin_id" required>
                    {% for b in todas_bins %}
                        <option value="{{ b.id }}">BIN: {{ b.numero_bin }} (Atual: R$ {{ "%.2f"|format(b.preco) }})</option>
                    {% endfor %}
                </select>
                <label>NOVO PREÇO UNITÁRIO (R$)</label>
                <input type="number" step="0.01" min="0.5" name="novo_preco" placeholder="Ex: 8.50" required>
                <button type="submit" class="btn-buy-action">Atualizar Preço</button>
            </form>
        </div>

        <div class="panel-box">
            <div class="panel-title" style="margin-bottom:12px; color:#f8fafc;">➕ Cadastrar Nova BIN</div>
            <form action="/admin/bin/nova" method="POST">
                <label>NÚMERO DA BIN (6 Dígitos)</label>
                <input type="text" name="numero_bin" placeholder="Ex: 406655" required>
                <label>PREÇO UNITÁRIO (R$)</label>
                <input type="number" step="0.01" name="preco" placeholder="5.00" required>
                <button type="submit" class="btn-buy-action">Cadastrar BIN</button>
            </form>
        </div>
    </div>

    <div class="panel-box">
        <div class="panel-title" style="margin-bottom:12px; color:#f8fafc;">📦 Abastecer Estoque por BIN</div>
        <form action="/admin/estoque/adicionar" method="POST">
            <label>SELECIONE A BIN</label>
            <select name="bin_id">
                {% for b in todas_bins %}
                    <option value="{{ b.id }}">BIN: {{ b.numero_bin }}</option>
                {% endfor %}
            </select>
            <label>ITENS GERADOS / GGs (1 por linha)</label>
            <textarea name="itens" rows="5" placeholder="Cole os itens aqui..." required></textarea>
            <button type="submit" class="btn-action" style="width:100%;">Adicionar Itens ao Estoque</button>
        </form>
    </div>
</div>
"""

def get_user_logged():
    if 'user_id' not in session:
        return None
    try:
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM usuarios WHERE id = ?", (session['user_id'],)).fetchone()
        conn.close()
        return user
    except Exception:
        return None

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    indicado_por = request.args.get('ref', '')
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        
        try:
            conn = get_db_connection()
            user = conn.execute("SELECT * FROM usuarios WHERE username = ?", (username,)).fetchone()
            conn.close()
            
            if user and check_password_hash(user['password'], password):
                session['user_id'] = user['id']
                return redirect('/')
            else:
                error = 'Usuário ou senha incorretos.'
        except Exception as e:
            error = f'Erro no banco de dados: {e}'
            
    return render_template_string(AUTH_HTML, title='Login', action='/login', error=error, indicado_por=indicado_por)

@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    indicado_por = request.args.get('ref', '')
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        ref_code = request.form.get('indicado_por', '').strip()
        
        if not username or not password:
            error = 'Preencha todos os campos.'
            return render_template_string(AUTH_HTML, title='Cadastro', action='/register', error=error, indicado_por=indicado_por)

        conn = get_db_connection()
        try:
            hashed_pw = generate_password_hash(password)
            is_admin = 1 if username == "S.lucas1" else 0
            conn.execute("INSERT INTO usuarios (username, password, is_admin, indicado_por) VALUES (?, ?, ?, ?)", 
                         (username, hashed_pw, is_admin, ref_code if ref_code else None))
            conn.commit()
            return redirect('/login')
        except sqlite3.IntegrityError:
            error = 'Nome de usuário já cadastrado.'
        except Exception as e:
            error = f'Erro interno: {e}'
        finally:
            conn.close()
            
    return render_template_string(AUTH_HTML, title='Cadastro', action='/register', error=error, indicado_por=indicado_por)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/')
def index():
    user = get_user_logged()
    if not user:
        return redirect('/login')
        
    erro = request.args.get('erro', None)

    try:
        conn = get_db_connection()
        bins_raw = conn.execute("SELECT id, numero_bin, preco_unitario FROM bins").fetchall()
        lista_bins = []
        estoque_total = 0
        
        for b in bins_raw:
            qtd = conn.execute("SELECT COUNT(*) FROM estoque WHERE bin_id = ? AND status = 'disponivel'", (b['id'],)).fetchone()[0]
            estoque_total += qtd
            if qtd > 0:
                lista_bins.append({"id": b['id'], "numero_bin": b['numero_bin'], "preco": b['preco_unitario'], "estoque": qtd})
            
        conn.close()
    except Exception as e:
        lista_bins = []
        estoque_total = 0
        erro = f"Erro ao carregar dados: {e}"

    link_afiliado = request.host_url.rstrip('/') + url_for('register', ref=user['username'])

    return render_template_string(INDEX_HTML, usuario=user, lista_bins=lista_bins, total_bins=len(lista_bins), estoque_total=estoque_total, erro=erro, link_afiliado=link_afiliado)

@app.route('/depositar', methods=['POST'])
def depositar():
    user = get_user_logged()
    if not user:
        return redirect('/login')
        
    try:
        valor = float(request.form.get('valor', 0))
        if valor >= 10.0:
            conn = get_db_connection()
            data_atual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn.execute("INSERT INTO depositos (usuario_id, valor, data_solicitacao) VALUES (?, ?, ?)",
                         (user['id'], valor, data_atual))
            conn.commit()
            conn.close()
    except Exception:
        pass
    return redirect('/')

@app.route('/comprar', methods=['POST'])
def comprar():
    user = get_user_logged()
    if not user:
        return redirect('/login')
        
    bin_id = request.form.get('bin_id')
    try:
        quantidade = int(request.form.get('quantidade', 1))
    except ValueError:
        quantidade = 1
    
    conn = get_db_connection()
    try:
        bin_data = conn.execute("SELECT numero_bin, preco_unitario FROM bins WHERE id = ?", (bin_id,)).fetchone()
        if not bin_data:
            conn.close()
            return redirect('/')
            
        numero_bin = bin_data['numero_bin']
        preco_unitario = bin_data['preco_unitario']
        custo_total = preco_unitario * quantidade
        
        user_db = conn.execute("SELECT saldo FROM usuarios WHERE id = ?", (user['id'],)).fetchone()
        if user_db['saldo'] < custo_total:
            conn.close()
            return redirect(f'/?erro=Saldo+insuficiente!+Custo:+R${custo_total:.2f}')
            
        itens = conn.execute("SELECT id, conteudo FROM estoque WHERE bin_id = ? AND status = 'disponivel' LIMIT ?", (bin_id, quantidade)).fetchall()
        
        if len(itens) < quantidade:
            conn.close()
            return redirect(f'/?erro=Estoque+insuficiente!+Apenas+{len(itens)}+disponiveis.')
            
        itens_entregues = []
        for item in itens:
            conn.execute("UPDATE estoque SET status = 'vendido' WHERE id = ?", (item['id'],))
            itens_entregues.append(item['conteudo'])
            
        novo_saldo = user_db['saldo'] - custo_total
        conn.execute("UPDATE usuarios SET saldo = ? WHERE id = ?", (novo_saldo, user['id']))
        conn.commit()
        
        salvar_saldo_arquivo(user['username'], novo_saldo, f"COMPRA_BIN_-R${custo_total:.2f}")
        registrar_historico_compra(user['id'], numero_bin, quantidade, custo_total, itens_entregues)
        atualizar_arquivo_estoque_geral()
        
        bins_raw = conn.execute("SELECT id, numero_bin, preco_unitario FROM bins").fetchall()
        lista_bins = []
        estoque_total = 0
        for b in bins_raw:
            qtd = conn.execute("SELECT COUNT(*) FROM estoque WHERE bin_id = ? AND status = 'disponivel'", (b['id'],)).fetchone()[0]
            estoque_total += qtd
            if qtd > 0:
                lista_bins.append({"id": b['id'], "numero_bin": b['numero_bin'], "preco": b['preco_unitario'], "estoque": qtd})
            
        user_updated = conn.execute("SELECT * FROM usuarios WHERE id = ?", (user['id'],)).fetchone()
        conn.close()
        
        link_afiliado = request.host_url.rstrip('/') + url_for('register', ref=user['username'])
        return render_template_string(INDEX_HTML, usuario=user_updated, lista_bins=lista_bins, total_bins=len(lista_bins), estoque_total=estoque_total, entregues=itens_entregues, link_afiliado=link_afiliado)
    except Exception as e:
        conn.rollback()
        conn.close()
        return redirect(f'/?erro=Erro+ao+processar+compra:+{e}')

@app.route('/admin_secret_lk')
def admin():
    user = get_user_logged()
    if not user or user['username'] != 'S.lucas1':
        return "Acesso Negado", 403
        
    msg = request.args.get('msg', None)
    
    # Parâmetros de filtro recebidos via GET
    filtro_usuario = request.args.get('filtro_usuario', '').strip()
    filtro_data_inicio = request.args.get('filtro_data_inicio', '').strip()
    filtro_data_fim = request.args.get('filtro_data_fim', '').strip()

    try:
        conn = get_db_connection()
        bins_raw = conn.execute("SELECT id, numero_bin, preco_unitario FROM bins").fetchall()
        todas_bins = [{"id": b['id'], "numero_bin": b['numero_bin'], "preco": b['preco_unitario']} for b in bins_raw]
        
        usuarios_raw = conn.execute("SELECT id, username, saldo FROM usuarios").fetchall()
        total_usuarios = len(usuarios_raw)
        
        depositos_raw = conn.execute("""
            SELECT d.id, u.username, d.valor, d.data_solicitacao 
            FROM depositos d 
            JOIN usuarios u ON u.id = d.usuario_id 
            WHERE d.status = 'pendente'
        """).fetchall()
        total_depositos_pendentes = len(depositos_raw)

        # Construção dinâmica da query de histórico com base nos filtros preenchidos
        query_hist = """
            SELECT h.id, u.username, h.bin_numero, h.quantidade, h.custo_total, h.itens, h.data_hora 
            FROM historico_compras h 
            JOIN usuarios u ON u.id = h.usuario_id 
            WHERE 1=1
        """
        params = []

        if filtro_usuario:
            query_hist += " AND u.username LIKE ?"
            params.append(f"%{filtro_usuario}%")

        if filtro_data_inicio:
            query_hist += " AND date(h.data_hora) >= ?"
            params.append(filtro_data_inicio)

        if filtro_data_fim:
            query_hist += " AND date(h.data_hora) <= ?"
            params.append(filtro_data_fim)

        # Se nenhum filtro de data foi especificado, aplica o padrão anterior (últimos 15 minutos) ou traz tudo? 
        # Aqui removemos a trava de 15 min quando há filtro ativo, ou mantemos histórico geral flexível. 
        # Vamos ordenar por ID decrescente para exibir as mais recentes primeiro.
        query_hist += " ORDER BY h.id DESC"

        historico_compras = conn.execute(query_hist, params).fetchall()

        conn.close()
    except Exception as e:
        print(f"Erro no admin: {e}")
        todas_bins, usuarios_raw, depositos_raw, historico_compras = [], [], [], []
        total_usuarios, total_depositos_pendentes = 0, 0

    return render_template_string(
        ADMIN_HTML, 
        todas_bins=todas_bins, 
        usuarios=usuarios_raw, 
        depositos=depositos_raw, 
        historico_compras=historico_compras, 
        mensagem=msg, 
        total_usuarios=total_usuarios, 
        total_depositos_pendentes=total_depositos_pendentes,
        filtro_usuario=filtro_usuario,
        filtro_data_inicio=filtro_data_inicio,
        filtro_data_fim=filtro_data_fim
    )

@app.route('/admin/deposito/aprovar/<int:deposito_id>')
def aprovar_deposito(deposito_id):
    user = get_user_logged()
    if not user or user['username'] != 'S.lucas1':
        return "Acesso Negado", 403
        
    conn = get_db_connection()
    try:
        dep = conn.execute("SELECT * FROM depositos WHERE id = ?", (deposito_id,)).fetchone()
        if dep and dep['status'] == 'pendente':
            usuario_id = dep['usuario_id']
            valor_dep = dep['valor']
            
            user_alvo = conn.execute("SELECT * FROM usuarios WHERE id = ?", (usuario_id,)).fetchone()
            depositos_aprovados_antigos = conn.execute("SELECT COUNT(*) FROM depositos WHERE usuario_id = ? AND status = 'aprovado'", (usuario_id,)).fetchone()[0]
            
            bonus_extra = 0.0
            if depositos_aprovados_antigos == 0 and user_alvo['indicado_por']:
                bonus_extra = 15.0
                indicador_nome = user_alvo['indicado_por']
                indicador = conn.execute("SELECT id, username, saldo FROM usuarios WHERE username = ?", (indicador_nome,)).fetchone()
                if indicador:
                    conn.execute("UPDATE usuarios SET saldo = saldo + 10.0 WHERE id = ?", (indicador['id'],))
                    salvar_saldo_arquivo(indicador['username'], indicador['saldo'] + 10.0, f"COMISSAO_AFILIADO_+R$10.00_DE_{user_alvo['username']}")

            total_credito = valor_dep + bonus_extra
            conn.execute("UPDATE usuarios SET saldo = saldo + ? WHERE id = ?", (total_credito, usuario_id))
            conn.execute("UPDATE depositos SET status = 'aprovado' WHERE id = ?", (deposito_id,))
            
            u = conn.execute("SELECT username, saldo FROM usuarios WHERE id = ?", (usuario_id,)).fetchone()
            msg_log = f"DEPOSITO_PIX_APROVADO_+R${valor_dep:.2f}"
            if bonus_extra > 0:
                msg_log += f"_COM_BONUS_INDICACAO_+R${bonus_extra:.2f}"
            salvar_saldo_arquivo(u['username'], u['saldo'], msg_log)
            conn.commit()
    except Exception as e:
        print(f"Erro ao aprovar depósito: {e}")
        conn.rollback()
    finally:
        conn.close()
    return redirect('/admin_secret_lk?msg=Depósito+aprovado+com+sucesso!')

@app.route('/admin/deposito/rejeitar/<int:deposito_id>')
def rejeitar_deposito(deposito_id):
    user = get_user_logged()
    if not user or user['username'] != 'S.lucas1':
        return "Acesso Negado", 403
        
    conn = get_db_connection()
    try:
        conn.execute("UPDATE depositos SET status = 'rejeitado' WHERE id = ?", (deposito_id,))
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        conn.close()
    return redirect('/admin_secret_lk?msg=Depósito+rejeitado!')

@app.route('/admin/usuario/saldo', methods=['POST'])
def alterar_saldo_manual():
    user = get_user_logged()
    if not user or user['username'] != 'S.lucas1':
        return "Acesso Negado", 403
        
    usuario_id = request.form.get('usuario_id')
    try:
        valor = float(request.form.get('valor', 0))
    except ValueError:
        valor = 0.0

    conn = get_db_connection()
    try:
        conn.execute("UPDATE usuarios SET saldo = saldo + ? WHERE id = ?", (valor, usuario_id))
        u = conn.execute("SELECT username, saldo FROM usuarios WHERE id = ?", (usuario_id,)).fetchone()
        salvar_saldo_arquivo(u['username'], u['saldo'], f"AJUSTE_MANUAL_+R${valor:.2f}")
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        conn.close()
    return redirect('/admin_secret_lk?msg=Saldo+atualizado+com+sucesso!')

@app.route('/admin/bin/editar', methods=['POST'])
def editar_bin():
    user = get_user_logged()
    if not user or user['username'] != 'S.lucas1':
        return "Acesso Negado", 403
        
    bin_id = request.form.get('bin_id')
    try:
        novo_preco = float(request.form.get('novo_preco'))
    except ValueError:
        novo_preco = 0.0
    
    conn = get_db_connection()
    try:
        conn.execute("UPDATE bins SET preco_unitario = ? WHERE id = ?", (novo_preco, bin_id))
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        conn.close()
    return redirect('/admin_secret_lk?msg=Preço+da+BIN+atualizado+com+sucesso!')

@app.route('/admin/bin/nova', methods=['POST'])
def nova_bin():
    user = get_user_logged()
    if not user or user['username'] != 'S.lucas1':
        return "Acesso Negado", 403
        
    numero_bin = request.form.get('numero_bin', '').strip()
    try:
        preco = float(request.form.get('preco', 0))
    except ValueError:
        preco = 0.0
    
    conn = get_db_connection()
    try:
        conn.execute("INSERT INTO bins (numero_bin, preco_unitario) VALUES (?, ?)", (numero_bin, preco))
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        conn.close()
    return redirect('/admin_secret_lk?msg=BIN+cadastrada+com+sucesso!')

@app.route('/admin/estoque/adicionar', methods=['POST'])
def adicionar_estoque():
    user = get_user_logged()
    if not user or user['username'] != 'S.lucas1':
        return "Acesso Negado", 403
        
    bin_id = request.form.get('bin_id')
    itens_texto = request.form.get('itens', '').strip()
    
    if itens_texto:
        linhas = itens_texto.split('\n')
        conn = get_db_connection()
        try:
            for linha in linhas:
                conteudo = linha.strip()
                if conteudo:
                    conn.execute("INSERT INTO estoque (bin_id, conteudo, status) VALUES (?, ?, 'disponivel')", (bin_id, conteudo))
            conn.commit()
        except Exception:
            conn.rollback()
        finally:
            conn.close()
        
        atualizar_arquivo_estoque_geral()
        
    return redirect('/admin_secret_lk?msg=Estoque+abastecido+com+sucesso!')

init_db()

if __name__ == '__main__':
    app.run(debug=True)
