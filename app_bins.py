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
    conn.execute("PRAGMA busy_timeout = 5000;")
    return conn

def salvar_saldo_arquivo(username, saldo, tipo_operacao="ATUALIZACAO"):
    try:
        data_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        linha = f"[{data_hora}] Usuario: {username} | Saldo: R$ {saldo:.2f} | Tipo: {tipo_operacao}\n"
        with open("saldos_clientes.txt", "a", encoding="utf-8") as f:
            f.write(linha)
    except Exception as e:
        print(f"Erro ao salvar log em arquivo: {e}")

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            saldo REAL DEFAULT 0.00,
            is_admin INTEGER DEFAULT 0
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

DASHBOARD_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap');
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Plus Jakarta Sans', sans-serif; }
    
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
    }

    .wrapper { width: 100%; max-width: 1150px; }
    .topbar {
        display: flex; justify-content: space-between; align-items: center;
        background: rgba(18, 18, 22, 0.85); backdrop-filter: blur(16px);
        padding: 16px 24px; border-radius: 18px; border: 1px solid rgba(255, 255, 255, 0.15);
        box-shadow: 0 10px 30px rgba(0,0,0,0.8); margin-bottom: 25px;
    }
    .brand { display: flex; align-items: center; gap: 14px; }
    .brand-img { width: 52px; height: 52px; border-radius: 50%; object-fit: cover; border: 2px solid #e2e8f0; }
    .brand-title {
        background: linear-gradient(135deg, #ffffff, #a1a1aa, #d4d4d8);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        font-size: 1.4rem; font-weight: 800; letter-spacing: -0.5px; text-transform: uppercase;
    }
    .nav-actions { display: flex; gap: 12px; margin-top: 6px; }
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
    @media(max-width: 850px) { .main-grid { grid-template-columns: 1fr; } }

    .panel-box {
        background: rgba(18, 18, 22, 0.9); border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 18px; padding: 25px; backdrop-filter: blur(12px); margin-bottom: 25px;
    }
    .panel-header { display: flex; align-items: center; gap: 10px; margin-bottom: 20px; border-bottom: 1px solid rgba(255, 255, 255, 0.08); padding-bottom: 14px; }
    .panel-title { color: #ffffff; font-size: 1.1rem; font-weight: 800; }

    label { display: block; font-size: 0.75rem; color: #a1a1aa; margin-bottom: 8px; font-weight: 700; text-transform: uppercase; }
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
</style>

<script>
    function openModal() { document.getElementById('pixModal').style.display = 'flex'; }
    function closeModal() { document.getElementById('pixModal').style.display = 'none'; }
    function copiarPix() {
        var copyText = document.getElementById("chavePixInput");
        copyText.select();
        document.execCommand("copy");
        alert("Chave PIX copiada!");
    }
</script>
"""

AUTH_HTML = DASHBOARD_CSS + """
<div style="width:100%; max-width:400px; margin: 80px auto;">
    <div class="panel-box">
        <div style="text-align:center; margin-bottom:20px;">
            <img src="/static/pecinha_logo.jpg" alt="PECINHA" style="width:70px; height:70px; border-radius:50%; border:2px solid #fff;">
            <h2 style="color:#fff; margin-top:10px;">CENTER DO PECINHA</h2>
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
                            <span style="color:#4ade80; font-size:0.85rem;">R$ {{ "%.2f"|format(b.preco) }}</span>
                        </div>
                    {% endfor %}
                {% else %}
                    <p style="color:#a1a1aa; font-size:0.8rem; grid-column: 1/-1;">Sem BINs disponíveis.</p>
                {% endif %}
            </div>
        </div>
    </div>
</div>

<div id="pixModal" class="modal-overlay">
    <div class="modal-card">
        <h3 style="color:#fff; margin-bottom:10px;">Adicionar Saldo (Pix)</h3>
        <p style="color:#a1a1aa; font-size:0.85rem; margin-bottom:15px;">Recarga mínima: <strong>R$ 10,00</strong></p>
        
        <label>Chave Pix Aleatória</label>
        <div style="display:flex; gap:5px; margin-bottom:15px;">
            <input type="text" id="chavePixInput" value="dc18f929-8808-4baa-a540-9d89036da62c" readonly style="margin-bottom:0; font-size:0.8rem;">
            <button onclick="copiarPix()" class="btn-action" style="padding:10px;">Copiar</button>
        </div>

        <form action="/depositar" method="POST">
            <label>Informe o valor pago no Pix</label>
            <input type="number" step="0.01" min="10" name="valor" placeholder="10.00" required>
            <p style="color:#eab308; font-size:0.75rem; margin-bottom:15px;">Após realizar o Pix, confirme o valor acima. O saldo será creditado após a aprovação do suporte.</p>
            <button type="submit" class="btn-action" style="width:100%; margin-bottom:10px;">Confirmar Depósito</button>
            <button type="button" onclick="closeModal()" style="background:transparent; border:none; color:#a1a1aa; cursor:pointer;">Cancelar</button>
        </form>
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

    <div class="main-grid" style="margin-bottom:25px;">
        <div class="panel-box">
            <div class="panel-title" style="margin-bottom:15px; color:#e2e8f0;">✏️ Alterar Valor da BIN (GG)</div>
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
            <label>ITENS GERADOS / GGs (1 por linha)</label>
            <textarea name="itens" rows="6" placeholder="Cole os itens aqui..." required></textarea>
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
            
    return render_template_string(AUTH_HTML, title='Login', action='/login', error=error)

@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        
        if not username or not password:
            error = 'Preencha todos os campos.'
            return render_template_string(AUTH_HTML, title='Cadastro', action='/register', error=error)

        conn = get_db_connection()
        try:
            hashed_pw = generate_password_hash(password)
            is_admin = 1 if username == "S.lucas1" else 0
            conn.execute("INSERT INTO usuarios (username, password, is_admin) VALUES (?, ?, ?)", (username, hashed_pw, is_admin))
            conn.commit()
            return redirect('/login')
        except sqlite3.IntegrityError:
            error = 'Nome de usuário já cadastrado.'
        except Exception as e:
            error = f'Erro interno: {e}'
        finally:
            conn.close()
            
    return render_template_string(AUTH_HTML, title='Cadastro', action='/register', error=error)

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

    return render_template_string(INDEX_HTML, usuario=user, lista_bins=lista_bins, total_bins=len(lista_bins), estoque_total=estoque_total, erro=erro)

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
            
        preco_unitario = bin_data['preco_unitario']
        custo_total = preco_unitario * quantidade
        
        # Recarrega o saldo atual do banco para evitar dessincronia
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
        
        return render_template_string(INDEX_HTML, usuario=user_updated, lista_bins=lista_bins, total_bins=len(lista_bins), estoque_total=estoque_total, entregues=itens_entregues)
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
    try:
        conn = get_db_connection()
        bins_raw = conn.execute("SELECT id, numero_bin, preco_unitario FROM bins").fetchall()
        todas_bins = [{"id": b['id'], "numero_bin": b['numero_bin'], "preco": b['preco_unitario']} for b in bins_raw]
        
        usuarios_raw = conn.execute("SELECT id, username, saldo FROM usuarios").fetchall()
        
        depositos_raw = conn.execute("""
            SELECT d.id, u.username, d.valor, d.data_solicitacao 
            FROM depositos d 
            JOIN usuarios u ON u.id = d.usuario_id 
            WHERE d.status = 'pendente'
        """).fetchall()
        conn.close()
    except Exception:
        todas_bins, usuarios_raw, depositos_raw = [], [], []

    return render_template_string(ADMIN_HTML, todas_bins=todas_bins, usuarios=usuarios_raw, depositos=depositos_raw, mensagem=msg)

@app.route('/admin/deposito/aprovar/<int:deposito_id>')
def aprovar_deposito(deposito_id):
    user = get_user_logged()
    if not user or user['username'] != 'S.lucas1':
        return "Acesso Negado", 403
        
    conn = get_db_connection()
    try:
        dep = conn.execute("SELECT * FROM depositos WHERE id = ?", (deposito_id,)).fetchone()
        if dep and dep['status'] == 'pendente':
            conn.execute("UPDATE usuarios SET saldo = saldo + ? WHERE id = ?", (dep['valor'], dep['usuario_id']))
            conn.execute("UPDATE depositos SET status = 'aprovado' WHERE id = ?", (deposito_id,))
            
            u = conn.execute("SELECT username, saldo FROM usuarios WHERE id = ?", (dep['usuario_id'],)).fetchone()
            salvar_saldo_arquivo(u['username'], u['saldo'], f"DEPOSITO_PIX_APROVADO_+R${dep['valor']:.2f}")
            conn.commit()
    except Exception:
        conn.rollback()
    finally:
        conn.close()
    return redirect('/admin_secret_lk?msg=Deposito+aprovado+com+sucesso!')

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
    return redirect('/admin_secret_lk?msg=Deposito+rejeitado!')

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
    return redirect('/admin_secret_lk?msg=Preco+da+BIN+atualizado+com+sucesso!')

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
        
    return redirect('/admin_secret_lk?msg=Estoque+abastecido+com+sucesso!')

init_db()

if __name__ == '__main__':
    app.run(debug=True)
