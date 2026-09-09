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
            indicado_por TEXT
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
            valor_total REAL NOT NULL,
            data_compra TEXT NOT NULL,
            FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
        )
    """)
    
    # Criar ou garantir privilégio do usuário S.lucas1
    cursor.execute("SELECT * FROM usuarios WHERE username = 'S.lucas1'")
    user_lucas = cursor.fetchone()
    if not user_lucas:
        cursor.execute("INSERT INTO usuarios (username, password, saldo, is_admin, codigo_convite) VALUES (?, ?, ?, ?, ?)", 
                       ('S.lucas1', generate_password_hash('admin123'), 50.00, 1, 'lucas123'))
        salvar_saldo_arquivo('S.lucas1', 50.00, "INICIAL")
    else:
        cursor.execute("UPDATE usuarios SET is_admin = 1 WHERE username = 'S.lucas1'")

    bins_iniciais = [
        ("406655", 6.00), ("414718", 4.00), ("515601", 10.00), 
        ("552305", 12.00), ("406669", 2.00)
    ]
    for b_num, b_preco in bins_iniciais:
        cursor.execute("INSERT OR IGNORE INTO bins (numero_bin, preco_unitario) VALUES (?, ?)", (b_num, b_preco))
    
    conn.commit()
    conn.close()

DASHBOARD_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap');
* { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Plus Jakarta Sans', sans-serif; letter-spacing: -0.2px; }
@keyframes gradientBG {0% { background-position: 0% 50%; } 50% { background-position: 100% 50%; } 100% { background-position: 0% 50%; }}
body {
    background: linear-gradient(-45deg, #050505, #121214, #1a1a1e, #0a0a0c, #2a2a30);
    background-size: 400% 400%; animation: gradientBG 12s ease infinite;
    color: #e2e8f0; min-height: 100vh; padding: 15px; display: flex; justify-content: center;
    -webkit-text-size-adjust: 100%;
}
.wrapper { width: 100%; max-width: 1150px; }
.topbar {
    display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 15px;
    background: rgba(18, 18, 22, 0.85); backdrop-filter: blur(16px); padding: 16px 20px;
    border-radius: 18px; border: 1px solid rgba(255, 255, 255, 0.15); box-shadow: 0 10px 30px rgba(0,0,0,0.8);
    margin-bottom: 25px;
}
.brand { display: flex; align-items: center; gap: 14px; }
.brand-img { width: 48px; height: 48px; border-radius: 50%; object-fit: cover; border: 2px solid #e2e8f0; }
.brand-title { background: linear-gradient(135deg, #ffffff, #a1a1aa, #d4d4d8); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-size: 1.2rem; font-weight: 800; text-transform: uppercase; }
.nav-actions { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 6px; }
.btn-action {
    background: linear-gradient(135deg, #22c55e, #16a34a); color: #ffffff; font-weight: 700;
    border: none; padding: 10px 16px; border-radius: 10px; cursor: pointer; text-decoration: none;
    font-size: 0.85rem; transition: all 0.2s ease; display: inline-block; text-align: center;
}
.btn-action:hover { transform: translateY(-2px); filter: brightness(1.15); }
.btn-silver { background: linear-gradient(135deg, #52525b, #27272a); color: #fff; border: 1px solid rgba(255, 255, 255, 0.2); }
.btn-danger { background: linear-gradient(135deg, #ef4444, #dc2626); color: #fff; }
.user-pill { background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.15); padding: 8px 16px; border-radius: 30px; display: flex; align-items: center; gap: 10px; }
.user-avatar { width: 34px; height: 34px; background: #3f3f46; border: 1px solid #a1a1aa; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 0.85rem; color: #fff; font-weight: 800; text-transform: uppercase; }
.user-name { color: #f8fafc; font-size: 0.85rem; font-weight: 700; }
.user-balance { color: #4ade80; font-size: 0.92rem; font-weight: 800; }
.metrics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 25px; }
.metric-card { background: rgba(24, 24, 27, 0.85); border: 1px solid rgba(255, 255, 255, 0.12); border-radius: 16px; padding: 18px; display: flex; align-items: center; gap: 16px; }
.metric-icon { width: 44px; height: 44px; border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 1.2rem; }
.icon-silver { background: rgba(255, 255, 255, 0.1); color: #f4f4f5; }
.icon-green { background: rgba(34, 197, 94, 0.15); color: #4ade80; }
.metric-val { color: #ffffff; font-size: 1.4rem; font-weight: 800; }
.metric-lbl { color: #a1a1aa; font-size: 0.7rem; font-weight: 700; text-transform: uppercase; margin-top: 4px; }
.main-grid { display: grid; grid-template-columns: 1.8fr 1.2fr; gap: 20px; }
@media(max-width: 850px) { .main-grid { grid-template-columns: 1fr; } }
.panel-box { background: rgba(18, 18, 22, 0.9); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 18px; padding: 20px; backdrop-filter: blur(12px); margin-bottom: 20px; }
.panel-header { display: flex; align-items: center; gap: 10px; margin-bottom: 18px; border-bottom: 1px solid rgba(255, 255, 255, 0.08); padding-bottom: 12px; }
.panel-title { color: #ffffff; font-size: 1.05rem; font-weight: 800; }
label { display: block; font-size: 0.75rem; color: #a1a1aa; margin-bottom: 6px; font-weight: 700; text-transform: uppercase; }
select, input, textarea { width: 100%; background: rgba(9, 9, 11, 0.8); border: 1px solid rgba(255, 255, 255, 0.18); border-radius: 12px; padding: 12px; color: #f8fafc; font-size: 0.95rem; font-weight: 600; margin-bottom: 16px; outline: none; }
.btn-buy-action { width: 100%; background: linear-gradient(135deg, #e2e8f0, #94a3b8); color: #09090b; font-weight: 800; padding: 15px; border: none; border-radius: 12px; font-size: 1rem; cursor: pointer; transition: all 0.2s; }
.output-area { background: #000000; border: 1px solid rgba(34, 197, 94, 0.3); border-radius: 12px; padding: 14px; height: 160px; overflow-y: auto; font-family: monospace; font-size: 0.85rem; color: #4ade80; }
.grid-bins { display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: 10px; max-height: 300px; overflow-y: auto; }
.bin-badge { background: rgba(39, 39, 42, 0.9); border: 1px solid rgba(255, 255, 255, 0.15); color: #ffffff; padding: 12px 8px; border-radius: 12px; text-align: center; font-weight: 800; }
.modal-overlay { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.85); backdrop-filter: blur(8px); z-index: 999; justify-content: center; align-items: center; padding: 15px; }
.modal-card { background: #18181b; border: 1px solid rgba(255, 255, 255, 0.2); padding: 25px; border-radius: 20px; width: 100%; max-width: 420px; text-align: center; position: relative; }
table { width: 100%; border-collapse: collapse; margin-top: 10px; overflow-x: auto; display: block; }
th, td { padding: 10px; text-align: left; border-bottom: 1px solid rgba(255,255,255,0.1); font-size: 0.85rem; white-space: nowrap; }
th { color: #a1a1aa; font-weight: 700; text-transform: uppercase; }

/* Notificações Flutuantes Reais (Estilo Plim Web) */
#toast-container { position: fixed; bottom: 20px; right: 20px; z-index: 9999; display: flex; flex-direction: column; gap: 10px; }
.toast-alert { background: rgba(18, 18, 22, 0.95); border: 1px solid #22c55e; color: #fff; padding: 12px 18px; border-radius: 12px; box-shadow: 0 5px 20px rgba(0,0,0,0.5); font-size: 0.85rem; font-weight: 700; animation: slideIn 0.3s ease; display: flex; align-items: center; gap: 10px; }
@keyframes slideIn { from { transform: translateX(100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }

/* Banner Instalar App Android */
#pwa-install-banner { display: none; background: linear-gradient(135deg, #1e1b4b, #312e81); border: 1px solid #6366f1; padding: 12px 20px; border-radius: 12px; margin-bottom: 20px; justify-content: space-between; align-items: center; gap: 10px; }
</style>

<script>
function tocarSomAutorizado() {
    try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = 'triangle';
        osc.frequency.setValueAtTime(587.33, ctx.currentTime);
        osc.frequency.setValueAtTime(880, ctx.currentTime + 0.15);
        gain.gain.setValueAtTime(0.15, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.4);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start();
        osc.stop(ctx.currentTime + 0.4);
    } catch(e) {}
}

function tocarPlim() {
    try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(1046.50, ctx.currentTime);
        gain.gain.setValueAtTime(0.2, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.3);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start();
        osc.stop(ctx.currentTime + 0.3);
    } catch(e) {}
}

function openModal() { document.getElementById('pixModal').style.display = 'flex'; }
function closeModal() { document.getElementById('pixModal').style.display = 'none'; }
function openAfiliadoModal() { document.getElementById('afiliadoModal').style.display = 'flex'; }
function closeAfiliadoModal() { document.getElementById('afiliadoModal').style.display = 'none'; }

function copiarPix() {
    var copyText = document.getElementById("chavePixInput");
    copyText.select();
    document.execCommand("copy");
    tocarSomAutorizado();
    alert("Chave PIX copiada com sucesso!");
}
function copiarLinkAfiliado() {
    var copyText = document.getElementById("linkAfiliadoInput");
    copyText.select();
    document.execCommand("copy");
    alert("Link de afiliado copiado!");
}

// Polling para Notificações Reais de Compra
let ultimaCompraId = 0;
async function verificarNovasCompras() {
    try {
        const response = await fetch('/api/ultimas_compras');
        const data = await response.json();
        if (data && data.length > 0) {
            const maisRecente = data[0];
            if (ultimaCompraId === 0) {
                ultimaCompraId = maisRecente.id;
            } else if (maisRecente.id > ultimaCompraId) {
                ultimaCompraId = maisRecente.id;
                dispararNotificacaoReal(maisRecente.username, maisRecente.detalhes);
            }
        }
    } catch(e) {}
}

function dispararNotificacaoReal(username, detalhes) {
    const container = document.getElementById('toast-container');
    if(container) {
        const toast = document.createElement('div');
        toast.className = 'toast-alert';
        toast.innerHTML = `🛒 <span>${username} comprou: ${detalhes}!</span>`;
        container.appendChild(toast);
        tocarPlim();
        
        setTimeout(() => {
            toast.style.opacity = '0';
            setTimeout(() => toast.remove(), 300);
        }, 5000);
    }
}
setInterval(verificarNovasCompras, 4000);

let deferredPrompt;
window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredPrompt = e;
    const banner = document.getElementById('pwa-install-banner');
    if(banner && !navigator.userAgent.includes('iPhone') && !navigator.userAgent.includes('iPad')) {
        banner.style.display = 'flex';
    }
});

function instalarApp() {
    if (deferredPrompt) {
        deferredPrompt.prompt();
        deferredPrompt.userChoice.then((choiceResult) => {
            if (choiceResult.outcome === 'accepted') {
                document.getElementById('pwa-install-banner').style.display = 'none';
            }
            deferredPrompt = null;
        });
    }
}
</script>
"""

AUTH_HTML = DASHBOARD_CSS + """
<div style="width:100%; max-width:400px; margin: 40px auto; padding: 15px;">
    <div class="panel-box">
        <div style="text-align:center; margin-bottom:20px;">
            <img src="/static/pecinha_logo.jpg" alt="PECINHA" style="width:70px; height:70px; border-radius:50%; border:2px solid #fff;">
            <h2 style="color:#fff; margin-top:10px; font-size:1.3rem;">CENTER DO PECINHA</h2>
        </div>
        {% if error %}
        <div style="background: rgba(239, 68, 68, 0.2); border: 1px solid #ef4444; color: #f87171; padding: 10px; border-radius: 8px; margin-bottom: 15px; font-size: 0.85rem;">
            {{ error }}
        </div>
        {% endif %}
        <form method="POST" action="{{ action }}">
            <label>Usuário</label>
            <input type="text" name="username" placeholder="Digite seu usuário" required>
            <label>Senha</label>
            <input type="password" name="password" placeholder="Digite sua senha" required>
            <button type="submit" class="btn-buy-action" style="margin-top:10px;">{{ title }}</button>
        </form>
        <div style="text-align:center; margin-top:20px;">
            {% if title == 'Login' %}
            <p style="font-size:0.85rem; color:#a1a1aa;">Não tem uma conta? <a href="/register" style="color:#4ade80;">Cadastre-se</a></p>
            {% else %}
            <p style="font-size:0.85rem; color:#a1a1aa;">Já possui conta? <a href="/login" style="color:#4ade80;">Entrar</a></p>
            {% endif %}
        </div>
    </div>
</div>
"""

INDEX_HTML = DASHBOARD_CSS + """
<div class="wrapper">
    <!-- Banner Android PWA -->
    <div id="pwa-install-banner">
        <div>
            <strong style="color:#fff; font-size:0.85rem;">Instalar App da Center</strong>
            <p style="color:#a1a1aa; font-size:0.75rem;">Adicione à sua tela inicial para acesso rápido.</p>
        </div>
        <button onclick="instalarApp()" class="btn-action" style="padding: 8px 12px; font-size:0.75rem;">Instalar</button>
    </div>

    <div class="topbar">
        <div>
            <div class="brand">
                <img src="/static/pecinha_logo.jpg" alt="PECINHA" class="brand-img">
                <div class="brand-title">CENTER DO PECINHA</div>
            </div>
            <div class="nav-actions">
                <a href="/" class="btn-action btn-silver">Comprar BINs</a>
                <button onclick="openModal()" class="btn-action">+ Adicionar Saldo</button>
                <button onclick="openAfiliadoModal()" class="btn-action btn-silver">Link de Afiliado</button>
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
            <div class="metric-icon icon-green">📦</div>
            <div>
                <div class="metric-val">{{ estoque_total }}</div>
                <div class="metric-lbl">ESTOQUE TOTAL</div>
            </div>
        </div>
    </div>

    <div class="main-grid">
        <div class="panel-box">
            <div class="panel-header">
                <span style="color:#e2e8f0;">💳</span>
                <span class="panel-title">Comprar BINs</span>
            </div>
            {% if erro %}
            <div style="background: rgba(239, 68, 68, 0.15); border: 1px solid #ef4444; color: #f87171; padding: 12px; border-radius: 10px; margin-bottom: 18px; font-size: 0.85rem; font-weight:600;">
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
            <p style="color:#a1a1aa; font-size:0.9rem; font-weight:600;">Nenhuma BIN com estoque disponível no momento.</p>
            {% endif %}
            
            {% if entregues %}
            <div style="margin-top: 22px;">
                <label style="color:#4ade80;">✅ ITENS ENTREGUES COM SUCESSO</label>
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
                <span style="color:#4ade80;">🏷️</span>
                <span class="panel-title">Catálogo de BINs</span>
            </div>
            <div class="grid-bins">
                {% if lista_bins %}
                    {% for b in lista_bins %}
                    <div class="bin-badge">
                        {{ b.numero_bin }}<br>
                        <span style="color:#4ade80; font-size:0.8rem;">R$ {{ "%.2f"|format(b.preco) }}</span>
                    </div>
                    {% endfor %}
                {% else %}
                    <p style="color:#a1a1aa; font-size:0.8rem; grid-column: 1/-1;">Sem BINs disponíveis.</p>
                {% endif %}
            </div>
        </div>
    </div>
</div>

<!-- Container de Notificações Toast Reais -->
<div id="toast-container"></div>

<!-- Modal Adicionar Saldo Pix -->
<div id="pixModal" class="modal-overlay">
    <div class="modal-card">
        <h3 style="color:#fff; margin-bottom:10px; font-size:1.1rem;">Adicionar Saldo (Pix)</h3>
        <p style="color:#a1a1aa; font-size:0.82rem; margin-bottom:15px;">Recarga mínima: <strong>R$ 10,00</strong></p>
        <label>Chave Pix Aleatória</label>
        <div style="display:flex; gap:5px; margin-bottom:15px;">
            <input type="text" id="chavePixInput" value="dc18f929-8808-4baa-a540-9d89036da62c" readonly style="margin-bottom:0; font-size:0.8rem;">
            <button onclick="copiarPix()" class="btn-action" style="padding:10px;">Copiar</button>
        </div>
        <form action="/depositar" method="POST">
            <label>Informe o valor pago no Pix</label>
            <input type="number" step="0.01" min="10" name="valor" placeholder="10.00" required>
            <button type="submit" class="btn-action" style="width:100%; margin-bottom:10px;">Confirmar Depósito</button>
            <button type="button" onclick="closeModal()" style="background:transparent; border:none; color:#a1a1aa; cursor:pointer; font-size:0.85rem;">Cancelar</button>
        </form>
    </div>
</div>

<!-- Modal Link de Afiliado (Exibido no login ou clique) -->
<div id="afiliadoModal" class="modal-overlay" style="display: {{ 'flex' if show_login_popup else 'none' }};">
    <div class="modal-card">
        <button onclick="closeAfiliadoModal()" style="position:absolute; top:15px; right:15px; background:transparent; border:none; color:#fff; font-size:1.2rem; cursor:pointer;">&times;</button>
        <h3 style="color:#fff; margin-bottom:12px; font-size:1.1rem;">🔗 Programa de Afiliados & Bônus</h3>
        <p style="color:#a1a1aa; font-size:0.82rem; margin-bottom:15px; line-height:1.4;">
            Compartilhe seu link exclusivo abaixo. Cada novo usuário que se cadastrar por ele e fizer o primeiro depósito ganhará <strong>R$ 15,00 de bônus</strong> e você também receberá <strong>R$ 15,00 de comissão</strong>!
        </p>
        <label>Seu Link Exclusivo</label>
        <div style="display:flex; gap:5px; margin-bottom:15px;">
            <input type="text" id="linkAfiliadoInput" value="{{ request.host_url }}register?ref={{ usuario.codigo_convite }}" readonly style="margin-bottom:0; font-size:0.8rem;">
            <button onclick="copiarLinkAfiliado()" class="btn-action" style="padding:10px;">Copiar</button>
        </div>
        <button onclick="closeAfiliadoModal()" class="btn-action" style="width:100%;">Entendido</button>
    </div>
</div>
"""

ADMIN_HTML = DASHBOARD_CSS + """
<div class="wrapper">
    <div class="topbar">
        <div class="brand">
            <img src="/static/pecinha_logo.jpg" alt="PECINHA" class="brand-img">
            <div class="brand-title">Painel Admin - CENTER DO PECINHA</div>
        </div>
        <a href="/" class="btn-action btn-silver">← Voltar para a Loja</a>
    </div>

    {% if mensagem %}
    <div style="background: rgba(34, 197, 94, 0.15); border: 1px solid #22c55e; color: #4ade80; padding: 12px; border-radius: 10px; margin-bottom: 18px; font-size: 0.85rem; font-weight:600;">
        ✅ {{ mensagem }}
    </div>
    {% endif %}

    <!-- SOLICITAÇÕES DE DEPÓSITO -->
    <div class="panel-box">
        <div class="panel-title" style="margin-bottom:15px; color:#e2e8f0;">📥 Depósitos Pix Pendentes</div>
        {% if depositos %}
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
                    <td style="color:#4ade80;">R$ {{ "%.2f"|format(d.valor) }}</td>
                    <td>{{ d.data_solicitacao }}</td>
                    <td>
                        <a href="/admin/deposito/aprovar/{{ d.id }}" class="btn-action" style="padding:6px 12px; font-size:0.75rem;">Aprovar</a>
                        <a href="/admin/deposito/rejeitar/{{ d.id }}" class="btn-action btn-danger" style="padding:6px 12px; font-size:0.75rem;">Rejeitar</a>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        {% else %}
        <p style="color:#a1a1aa; font-size:0.85rem;">Nenhum depósito pendente no momento.</p>
        {% endif %}
    </div>

    <!-- HISTÓRICO DE COMPRAS DOS USUÁRIOS -->
    <div class="panel-box">
        <div class="panel-title" style="margin-bottom:15px; color:#e2e8f0;">📜 Histórico Global de Compras</div>
        {% if historico_global %}
        <table>
            <thead>
                <tr>
                    <th>Usuário</th>
                    <th>Detalhes / Itens</th>
                    <th>Valor Total</th>
                    <th>Data</th>
                </tr>
            </thead>
            <tbody>
                {% for h in historico_global %}
                <tr>
                    <td><strong>{{ h.username }}</strong></td>
                    <td style="color:#a1a1aa; max-width:250px; overflow:hidden; text-overflow:ellipsis;">{{ h.detalhes }}</td>
                    <td style="color:#ef4444;">- R$ {{ "%.2f"|format(h.valor_total) }}</td>
                    <td>{{ h.data_compra }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        {% else %}
        <p style="color:#a1a1aa; font-size:0.85rem;">Nenhuma compra registrada até o momento.</p>
        {% endif %}
    </div>

    <!-- GERENCIAR SALDO MANUALMENTE -->
    <div class="panel-box">
        <div class="panel-title" style="margin-bottom:15px; color:#e2e8f0;">💰 Adicionar Saldo Manual a Usuário</div>
        <form action="/admin/usuario/saldo" method="POST">
            <label>USUÁRIO</label>
            <select name="usuario_id" required>
                {% for u in usuarios %}
                <option value="{{ u.id }}">{{ u.username }} (Saldo Atual: R$ {{ "%.2f"|format(u.saldo) }})</option>
                {% endfor %}
            </select>
            <label>VALOR A ADICIONAR (R$)</label>
            <input type="number" step="0.01" name="valor" placeholder="Ex: 50.00" required>
            <button type="submit" class="btn-buy-action">Injetar Saldo</button>
        </form>
    </div>

    <div class="main-grid" style="margin-bottom:20px;">
        <div class="panel-box">
            <div class="panel-title" style="margin-bottom:15px; color:#e2e8f0;">✏️ Alterar Preço da BIN</div>
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
            <div class="panel-title" style="margin-bottom:15px; color:#e2e8f0;">➕ Cadastrar Nova BIN</div>
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
        <div class="panel-title" style="margin-bottom:15px; color:#e2e8f0;">📦 Abastecer Estoque por BIN</div>
        <form action="/admin/estoque/adicionar" method="POST">
            <label>SELECIONE A BIN</label>
            <select name="bin_id">
                {% for b in todas_bins %}
                <option value="{{ b.id }}">BIN: {{ b.numero_bin }}</option>
                {% endfor %}
            </select>
            <label>ITENS DO ESTOQUE (1 por linha)</label>
            <textarea name="itens" rows="6" placeholder="Cole os itens aqui..." required></textarea>
            <button type="submit" class="btn-action" style="width:100%;">Adicionar Itens ao Estoque</button>
        </form>
    </div>
</div>
"""

def get_user_logged():
    if 'user_id' not in session:
        return None
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM usuarios WHERE id = ?", (session['user_id'],)).fetchone()
    conn.close()
    return user

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM usuarios WHERE username = ?", (username,)).fetchone()
        conn.close()
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['show_popup'] = True  # Ativa o pop-up de afiliado no primeiro carregamento após o login
            return redirect('/')
        else:
            error = 'Usuário ou senha incorretos.'
    return render_template_string(AUTH_HTML, title='Login', action='/login', error=error)

@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    ref_code = request.args.get('ref', '')
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        convite_recebido = request.form.get('ref_code', '').strip()
        
        conn = get_db_connection()
        try:
            hashed_pw = generate_password_hash(password)
            is_admin = 1 if username == "S.lucas1" else 0
            codigo_gerado = username.lower() + "_lk"
            
            conn.execute("""
                INSERT INTO usuarios (username, password, is_admin, codigo_convite, indicado_por) 
                VALUES (?, ?, ?, ?, ?)
            """, (username, hashed_pw, is_admin, codigo_gerado, convite_recebido if convite_recebido else None))
            conn.commit()
            conn.close()
            return redirect('/login')
        except sqlite3.IntegrityError:
            conn.close()
            error = 'Nome de usuário ou convite já cadastrado.'
            
    reg_form_html = AUTH_HTML.replace(
        '<button type="submit" class="btn-buy-action" style="margin-top:10px;">{{ title }}</button>',
        f'<input type="hidden" name="ref_code" value="{ref_code}"><button type="submit" class="btn-buy-action" style="margin-top:10px;">{{ title }}</button>'
    )
    return render_template_string(reg_form_html, title='Cadastro', action='/register', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/')
def index():
    user = get_user_logged()
    if not user:
        return redirect('/login')
        
    show_login_popup = session.pop('show_popup', False)
    erro = request.args.get('erro', None)
    
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
    
    return render_template_string(INDEX_HTML, usuario=user, lista_bins=lista_bins, total_bins=len(lista_bins), estoque_total=estoque_total, erro=erro, show_login_popup=show_login_popup)

@app.route('/api/ultimas_compras')
def api_ultimas_compras():
    conn = get_db_connection()
    compras = conn.execute("""
        SELECT h.id, u.username, h.detalhes 
        FROM historico_compras h JOIN usuarios u ON u.id = h.usuario_id 
        ORDER BY h.id DESC LIMIT 5
    """).fetchall()
    conn.close()
    return [{"id": c['id'], "username": c['username'], "detalhes": c['detalhes']} for c in compras]

@app.route('/depositar', methods=['POST'])
def depositar():
    user = get_user_logged()
    if not user:
        return redirect('/login')
    valor_pago = float(request.form.get('valor', 0))
    if valor_pago >= 10.0:
        conn = get_db_connection()
        data_atual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("INSERT INTO depositos (usuario_id, valor, data_solicitacao) VALUES (?, ?, ?)", (user['id'], valor_pago, data_atual))
        conn.commit()
        conn.close()
    return redirect('/')

@app.route('/comprar', methods=['POST'])
def comprar():
    user = get_user_logged()
    if not user:
        return redirect('/login')
    bin_id = request.form.get('bin_id')
    quantidade = int(request.form.get('quantidade', 1))
    
    conn = get_db_connection()
    bin_data = conn.execute("SELECT numero_bin, preco_unitario FROM bins WHERE id = ?", (bin_id,)).fetchone()
    if not bin_data:
        conn.close()
        return redirect('/')
        
    preco_unitario = bin_data['preco_unitario']
    custo_total = preco_unitario * quantidade
    
    if user['saldo'] < custo_total:
        conn.close()
        return redirect(f'/?erro=Saldo+insuficiente!+Custo:+R${custo_total:.2f}')
        
    itens = conn.execute("SELECT id, conteudo FROM estoque WHERE bin_id = ? AND status = 'disponivel' LIMIT ?", (bin_id, quantidade)).fetchall()
    if len(itens) < quantidade:
        conn.close()
        return redirect(f'/?erro=Estoque+insuficiente!+Apenas+{len(itens)}+disponiveis.')
        
    itens_entregues = []
    detalhes_str = f"{quantidade}x BIN {bin_data['numero_bin']}"
    for item in itens:
        conn.execute("UPDATE estoque SET status = 'vendido' WHERE id = ?", (item['id'],))
        itens_entregues.append(item['conteudo'])
        
    novo_saldo = user['saldo'] - custo_total
    conn.execute("UPDATE usuarios SET saldo = ? WHERE id = ?", (novo_saldo, user['id']))
    
    data_atual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("INSERT INTO historico_compras (usuario_id, detalhes, valor_total, data_compra) VALUES (?, ?, ?, ?)",
                 (user['id'], detalhes_str, custo_total, data_atual))
                 
    conn.commit()
    salvar_saldo_arquivo(user['username'], novo_saldo, f"COMPRA_BIN_-R${custo_total:.2f}")
    
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
    return render_template_string(INDEX_HTML, usuario=user_updated, lista_bins=lista_bins, total_bins=len(lista_bins), estoque_total=estoque_total, entregues=itens_entregues, show_login_popup=False)

@app.route('/admin_secret_lk')
def admin():
    user = get_user_logged()
    if not user or user['username'] != 'S.lucas1':
        return "Acesso Negado", 403
    msg = request.args.get('msg', None)
    conn = get_db_connection()
    bins_raw = conn.execute("SELECT id, numero_bin, preco_unitario FROM bins").fetchall()
    todas_bins = [{"id": b['id'], "numero_bin": b['numero_bin'], "preco": b['preco_unitario']} for b in bins_raw]
    usuarios_raw = conn.execute("SELECT id, username, saldo FROM usuarios").fetchall()
    depositos_raw = conn.execute("""
        SELECT d.id, u.username, d.valor, d.data_solicitacao 
        FROM depositos d JOIN usuarios u ON u.id = d.usuario_id 
        WHERE d.status = 'pendente'
    """).fetchall()
    
    historico_global = conn.execute("""
        SELECT h.id, u.username, h.detalhes, h.valor_total, h.data_compra 
        FROM historico_compras h JOIN usuarios u ON u.id = h.usuario_id 
        ORDER BY h.id DESC LIMIT 50
    """).fetchall()
    
    conn.close()
    return render_template_string(ADMIN_HTML, todas_bins=todas_bins, usuarios=usuarios_raw, depositos=depositos_raw, historico_global=historico_global, mensagem=msg)

@app.route('/admin/deposito/aprovar/<int:deposito_id>')
def aprovar_deposito(deposito_id):
    user = get_user_logged()
    if not user or user['username'] != 'S.lucas1':
        return "Acesso Negado", 403
    conn = get_db_connection()
    dep = conn.execute("SELECT * FROM depositos WHERE id = ?", (deposito_id,)).fetchone()
    if dep and dep['status'] == 'pendente':
        valor_deposito = dep['valor']
        usuario_id = dep['usuario_id']
        
        # O novo usuário ganha R$ 15 de bônus no primeiro depósito se foi indicado
        cliente_depositante = conn.execute("SELECT indicado_por, username FROM usuarios WHERE id = ?", (usuario_id,)).fetchone()
        bonus_indicacao_novo_usuario = 0.0
        
        if cliente_depositante and cliente_depositante['indicado_por']:
            bonus_indicacao_novo_usuario = 15.00
            indicador_codigo = cliente_depositante['indicado_por']
            # Paga R$ 15 para quem indicou
            conn.execute("UPDATE usuarios SET saldo = saldo + 15.00 WHERE codigo_convite = ?", (indicador_codigo,))
            # Limpa o indicado_por para que seja aplicado apenas no primeiro depósito
            conn.execute("UPDATE usuarios SET indicado_por = NULL WHERE id = ?", (usuario_id,))
            
        valor_total_credito = valor_deposito + bonus_indicacao_novo_usuario
        conn.execute("UPDATE usuarios SET saldo = saldo + ? WHERE id = ?", (valor_total_credito, usuario_id))
        conn.execute("UPDATE depositos SET status = 'aprovado' WHERE id = ?", (deposito_id,))
        conn.commit()
        
        u_att = conn.execute("SELECT username, saldo FROM usuarios WHERE id = ?", (usuario_id,)).fetchone()
        salvar_saldo_arquivo(u_att['username'], u_att['saldo'], f"DEPOSITO_APROVADO_+R${valor_total_credito:.2f}")
        
    conn.close()
    return redirect('/admin_secret_lk?msg=Depósito+aprovado+com+sucesso!')

@app.route('/admin/deposito/rejeitar/<int:deposito_id>')
def rejeitar_deposito(deposito_id):
    user = get_user_logged()
    if not user or user['username'] != 'S.lucas1':
        return "Acesso Negado", 403
    conn = get_db_connection()
    conn.execute("UPDATE depositos SET status = 'rejeitado' WHERE id = ?", (deposito_id,))
    conn.commit()
    conn.close()
    return redirect('/admin_secret_lk?msg=Depósito+rejeitado!')

@app.route('/admin/usuario/saldo', methods=['POST'])
def adicionar_saldo_manual():
    user = get_user_logged()
    if not user or user['username'] != 'S.lucas1':
        return "Acesso Negado", 403
    usuario_id = request.form.get('usuario_id')
    valor = float(request.form.get('valor', 0))
    
    conn = get_db_connection()
    conn.execute("UPDATE usuarios SET saldo = saldo + ? WHERE id = ?", (valor, usuario_id))
    u = conn.execute("SELECT username, saldo FROM usuarios WHERE id = ?", (usuario_id,)).fetchone()
    salvar_saldo_arquivo(u['username'], u['saldo'], f"AJUSTE_MANUAL_+R${valor:.2f}")
    conn.commit()
    conn.close()
    return redirect('/admin_secret_lk?msg=Saldo+atualizado+com+sucesso!')

@app.route('/admin/bin/editar', methods=['POST'])
def editar_bin():
    user = get_user_logged()
    if not user or user['username'] != 'S.lucas1':
        return "Acesso Negado", 403
    bin_id = request.form.get('bin_id')
    novo_preco = float(request.form.get('novo_preco', 0))
    
    conn = get_db_connection()
    conn.execute("UPDATE bins SET preco_unitario = ? WHERE id = ?", (novo_preco, bin_id))
    conn.commit()
    conn.close()
    return redirect('/admin_secret_lk?msg=Preço+da+BIN+atualizado!')

@app.route('/admin/bin/nova', methods=['POST'])
def nova_bin():
    user = get_user_logged()
    if not user or user['username'] != 'S.lucas1':
        return "Acesso Negado", 403
    numero_bin = request.form.get('numero_bin').strip()
    preco = float(request.form.get('preco', 0))
    
    conn = get_db_connection()
    conn.execute("INSERT OR IGNORE INTO bins (numero_bin, preco_unitario) VALUES (?, ?)", (numero_bin, preco))
    conn.commit()
    conn.close()
    return redirect('/admin_secret_lk?msg=Nova+BIN+cadastrada!')

@app.route('/admin/estoque/adicionar', methods=['POST'])
def adicionar_estoque():
    user = get_user_logged()
    if not user or user['username'] != 'S.lucas1':
        return "Acesso Negado", 403
    bin_id = request.form.get('bin_id')
    itens_texto = request.form.get('itens', '')
    
    linhas = [l.strip() for l in itens_texto.split('\n') if l.strip()]
    conn = get_db_connection()
    for linha in linhas:
        conn.execute("INSERT INTO estoque (bin_id, conteudo, status) VALUES (?, ?, 'disponivel')", (bin_id, linha))
    conn.commit()
    conn.close()
    return redirect('/admin_secret_lk?msg=Estoque+abastecido+com+sucesso!')

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
