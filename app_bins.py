import os
import sqlite3
import string
import random
from flask import Flask, render_template_string, request, redirect, url_for, session, flash

app = Flask(__name__)
app.secret_key = os.urandom(24)
DB_NAME = "database.db"

# --- BANCO DE DADOS ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Tabela de Usuários com suporte a Afiliados
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            balance REAL DEFAULT 0.0,
            bonus_balance REAL DEFAULT 0.0,
            referral_code TEXT UNIQUE NOT NULL,
            referred_by TEXT,
            deposit_made INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def generate_referral_code(length=6):
    chars = string.ascii_uppercase + string.digits
    while True:
        code = ''.join(random.choices(chars, k=length))
        db = get_db()
        exists = db.execute("SELECT id FROM users WHERE referral_code = ?", (code,)).fetchone()
        db.close()
        if not exists:
            return code

# --- ROTAS ---

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password)).fetchone()
        db.close()
        
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('dashboard'))
        flash('Usuário ou senha incorretos!', 'danger')
    return render_template_string(LOGIN_HTML)

@app.route('/register', methods=['GET', 'POST'])
def register():
    ref_code = request.args.get('ref', '')
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        used_ref = request.form.get('ref_code', '').strip()
        
        db = get_db()
        
        # Verifica se o usuário já existe
        existing = db.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if existing:
            db.close()
            flash('Este nome de usuário já está em uso.', 'danger')
            return redirect(url_for('register', ref=used_ref))
        
        my_ref_code = generate_referral_code()
        referred_by_user = None
        
        if used_ref:
            ref_user = db.execute("SELECT username FROM users WHERE referral_code = ?", (used_ref,)).fetchone()
            if ref_user:
                referred_by_user = ref_user['username']
                # Bônus imediato de R$ 15,00 para o novo usuário ao cadastrar pelo link
                initial_bonus = 15.0
            else:
                initial_bonus = 0.0
        else:
            initial_bonus = 0.0

        db.execute('''
            INSERT INTO users (username, password, bonus_balance, referral_code, referred_by)
            VALUES (?, ?, ?, ?, ?)
        ''', (username, password, initial_bonus, my_ref_code, referred_by_user))
        db.commit()
        db.close()
        
        flash('Conta criada com sucesso! Você ganhou R$ 15,00 de bônus de boas-vindas/indicação!', 'success')
        return redirect(url_for('login'))
        
    return render_template_string(REGISTER_HTML, ref_code=ref_code)

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],)).fetchone()
    
    # Contar quantos indicados este usuário possui
    referrals_count = db.execute("SELECT COUNT(*) as count FROM users WHERE referred_by = ?", (user['username'],)).fetchone()['count']
    db.close()
    
    ref_link = request.host_url + 'register?ref=' + user['referral_code']
    
    return render_template_string(DASHBOARD_HTML, user=user, ref_link=ref_link, referrals_count=referrals_count)

@app.route('/simulate_deposit', methods=['POST'])
def simulate_deposit():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],)).fetchone()
    
    # Simula um depósito de R$ 50,00
    deposit_amount = 50.0
    db.execute("UPDATE users SET balance = balance + ?, deposit_made = 1 WHERE id = ?", (deposit_amount, user['id']))
    
    # Regra do Afiliado: Se ele foi indicado por alguém e é o primeiro depósito, o padrinho ganha R$ 15,00
    if user['referred_by'] and user['deposit_made'] == 0:
        # Padrinho ganha 15 reais
        db.execute("UPDATE users SET balance = balance + 15.0 WHERE username = ?", (user['referred_by'],))
        flash(f'Depósito simulado com sucesso! Seu indicador ({user['referred_by']}) recebeu R$ 15,00 de comissão.', 'success')
    else:
        flash('Depósito simulado com sucesso!', 'success')
        
    db.commit()
    db.close()
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- TEMPLATES HTML EMBUTIDOS (DESIGN MODERNO) ---

LAYOUT_STYLE = """
<style>
    body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #0f172a; color: #f8fafc; margin: 0; padding: 0; display: flex; justify-content: center; align-items: center; height: 100vh; }
    .card { background: #1e293b; padding: 30px; border-radius: 12px; box-shadow: 0 10px 25px rgba(0,0,0,0.3); width: 100%; max-width: 450px; text-align: center; }
    input { width: 100%%; padding: 12px; margin: 10px 0; border: 1px solid #334155; border-radius: 6px; background: #0f172a; color: #fff; box-sizing: border-box; }
    button { background: #3b82f6; color: white; border: none; padding: 12px; width: 100%%; border-radius: 6px; cursor: pointer; font-weight: bold; margin-top: 10px; }
    button:hover { background: #2563eb; }
    a { color: #60a5fa; text-decoration: none; }
    .alert { padding: 10px; margin-bottom: 15px; border-radius: 6px; font-size: 14px; }
    .alert-danger { background: #7f1d1d; color: #fca5a5; }
    .alert-success { background: #14532d; color: #86efac; }
    .stats-box { background: #0f172a; padding: 15px; border-radius: 8px; margin: 15px 0; text-align: left; }
    .ref-input { background: #334155; border: none; padding: 8px; font-size: 12px; text-align: center; color: #cbd5e1; }
</style>
"""

LOGIN_HTML = f"""
<!DOCTYPE html>
<html>
<head><title>Login</title>{LAYOUT_STYLE}</head>
<body>
    <div class="card">
        <h2>Entrar na Plataforma</h2>
        {% with messages = get_flashed_messages(with_categories=true) %}
          {% if messages %}{% for category, message in messages %}<div class="alert alert-{{ category }}">{{ message }}</div>{% endfor %}{% endif %}
        {% endwith %}
        <form method="POST">
            <input type="text" name="username" placeholder="Usuário" required>
            <input type="password" name="password" placeholder="Senha" required>
            <button type="submit">Entrar</button>
        </form>
        <p style="margin-top: 20px;">Não tem uma conta? <a href="/register">Cadastre-se</a></p>
    </div>
</body>
</html>
"""

REGISTER_HTML = f"""
<!DOCTYPE html>
<html>
<head><title>Cadastro</title>{LAYOUT_STYLE}</head>
<body>
    <div class="card">
        <h2>Criar Conta</h2>
        {% with messages = get_flashed_messages(with_categories=true) %}
          {% if messages %}{% for category, message in messages %}<div class="alert alert-{{ category }}">{{ message }}</div>{% endfor %}{% endif %}
        {% endwith %}
        <form method="POST">
            <input type="text" name="username" placeholder="Escolha um Usuário" required>
            <input type="password" name="password" placeholder="Escolha uma Senha" required>
            <input type="hidden" name="ref_code" value="{{ ref_code }}">
            <button type="submit">Cadastrar</button>
        </form>
        <p style="margin-top: 20px;">Já tem uma conta? <a href="/login">Faça Login</a></p>
    </div>
</body>
</html>
"""

DASHBOARD_HTML = f"""
<!DOCTYPE html>
<html>
<head><title>Painel</title>{LAYOUT_STYLE}</head>
<body>
    <div class="card" style="max-width: 550px;">
        <h2>Olá, {{ user['username'] }}!</h2>
        {% with messages = get_flashed_messages(with_categories=true) %}
          {% if messages %}{% for category, message in messages %}<div class="alert alert-{{ category }}">{{ message }}</div>{% endfor %}{% endif %}
        {% endwith %>
        
        <div class="stats-box">
            <p><strong>Saldo Principal:</strong> R$ {{ "%.2f"|format(user['balance']) }}</p>
            <p><strong>Saldo de Bônus:</strong> R$ {{ "%.2f"|format(user['bonus_balance']) }}</p>
            <p><strong>Usuários indicados:</strong> {{ referrals_count }}</p>
        </div>

        <div class="stats-box">
            <p style="font-size: 13px; margin-bottom: 5px;"><strong>Seu Link de Indicação (Afiliado):</strong></p>
            <input type="text" class="ref-input" value="{{ ref_link }}" readonly onclick="this.select();">
            <p style="font-size: 11px; color: #94a3b8; margin-top: 5px;">Quem se cadastrar pelo seu link ganha R$ 15 e você ganha R$ 15 quando ele depositar!</p>
        </div>

        <form action="/simulate_deposit" method="POST">
            <button type="submit" style="background: #10b981;">Simular Depósito (R$ 50)</button>
        </form>
        
        <br>
        <a href="/logout" style="color: #ef4444;">Sair da conta</a>
    </div>
</body>
</html>
"""

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
