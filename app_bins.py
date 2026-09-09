import sqlite3
import os
import uuid
from datetime import datetime
from flask import Flask, render_template_string, request, redirect, session, url_for
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'sua_chave_secreta_super_segura_lk'
DB_PATH = "loja_pecinha.db"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

def init_db():
    conn = get_db_connection()
    # Tabela de usuários com suporte a código de afiliado e flag de admin
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            is_admin INTEGER DEFAULT 0,
            affiliate_code TEXT UNIQUE
        )
    ''')
    
    # Tabela para salvar cada usuário/depósito feito via link de afiliado
    conn.execute('''
        CREATE TABLE IF NOT EXISTS affiliate_deposits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            affiliate_code TEXT NOT NULL,
            username TEXT NOT NULL,
            amount REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Garante que colunas novas existam caso o banco já tenha sido criado antes
    try:
        conn.execute('ALTER TABLE users ADD COLUMN affiliate_code TEXT UNIQUE')
    except sqlite3.OperationalError:
        pass
        
    try:
        conn.execute('ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0')
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()

init_db()

# Rota de Captura de Afiliado (Quando alguém clica no link de indicação)
@app.route('/ref/<code>')
def ref_redirect(code):
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE affiliate_code = ?', (code,)).fetchone()
    conn.close()
    
    if user:
        session['ref_code'] = code  # Salva o código de quem indicou na sessão do visitante
    
    return redirect('/')

# Correção da rota do Admin para evitar Erro 500 caso o usuário não esteja logado ou não seja admin
@app.route('/admin_secret_lk')
def admin_secret_lk():
    if 'username' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE username = ?', (session['username'],)).fetchone()
    
    if not user or user['is_admin'] != 1:
        conn.close()
        return "Acesso negado. Você não tem permissão de administrador.", 403
        
    users = conn.execute('SELECT * FROM users').fetchall()
    deposits = conn.execute('SELECT * FROM affiliate_deposits ORDER BY created_at DESC').fetchall()
    conn.close()
    
    # Painel administrativo funcional integrando as listagens
    return render_template_string("""
        <!DOCTYPE html>
        <html lang="pt-br">
        <head>
            <meta charset="UTF-8">
            <title>Painel Admin - LK Center</title>
            <style>
                body { font-family: Arial, sans-serif; background: #f4f4f9; margin: 0; padding: 20px; color: #333; }
                h1, h2 { color: #222; }
                .container { max-width: 1000px; margin: auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
                table { width: 100%; border-collapse: collapse; margin-top: 15px; }
                th, td { padding: 10px; border: 1px solid #ddd; text-align: left; }
                th { background-color: #007bff; color: white; }
                a { color: #007bff; text-decoration: none; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Painel Administrativo Restrito</h1>
                <p>Logado como: <strong>{{ session['username'] }}</strong> | <a href="/logout">Sair</a></p>
                
                <h2>Usuários Cadastrados & Links</h2>
                <table>
                    <tr>
                        <th>ID</th>
                        <th>Usuário</th>
                        <th>Admin?</th>
                        <th>Código de Afiliado</th>
                    </tr>
                    {% for u in users %}
                    <tr>
                        <td>{{ u['id'] }}</td>
                        <td>{{ u['username'] }}</td>
                        <td>{{ 'Sim' if u['is_admin'] == 1 else 'Não' }}</td>
                        <td>{{ u['affiliate_code'] or 'N/A' }}</td>
                    </tr>
                    {% endfor %}
                </table>

                <h2>Depósitos Realizados via Afiliados</h2>
                <table>
                    <tr>
                        <th>ID</th>
                        <th>Código Afiliado</th>
                        <th>Usuário que Depositou</th>
                        <th>Valor (R$)</th>
                        <th>Data/Hora</th>
                    </tr>
                    {% for d in deposits %}
                    <tr>
                        <td>{{ d['id'] }}</td>
                        <td>{{ d['affiliate_code'] }}</td>
                        <td>{{ d['username'] }}</td>
                        <td>R$ {{ "%.2f"|format(d['amount']) }}</td>
                        <td>{{ d['created_at'] }}</td>
                    </tr>
                    {% endfor %}
                </table>
            </div>
        </body>
        </html>
    """, users=users, deposits=deposits)

# Exemplo de rota de Registro gerando automaticamente o link exclusivo de afiliado
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            return "Preencha todos os campos!", 400
            
        hashed_password = generate_password_hash(password)
        # Cria um código de afiliado único combinando o nome do usuário e caracteres aleatórios
        affiliate_code = f"{username.lower().strip().replace(' ', '_')}_{uuid.uuid4().hex[:4]}"
        
        conn = get_db_connection()
        try:
            conn.execute(
                'INSERT INTO users (username, password, affiliate_code, is_admin) VALUES (?, ?, ?, ?)',
                (username, hashed_password, affiliate_code, 0)
            )
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            return "Nome de usuário já existe!", 400
        conn.close()
        return redirect(url_for('login'))
        
    return render_template_string("""
        <form method="POST">
            <h2>Cadastro</h2>
            <input type="text" name="username" placeholder="Usuário" required><br><br>
            <input type="password" name="password" placeholder="Senha" required><br><br>
            <button type="submit">Cadastrar</button>
        </form>
    """)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        
        if user and check_password_hash(user['password'], password):
            session['username'] = user['username']
            return redirect(url_for('dashboard'))
        return "Credenciais inválidas!", 401
        
    return render_template_string("""
        <form method="POST">
            <h2>Login</h2>
            <input type="text" name="username" placeholder="Usuário" required><br><br>
            <input type="password" name="password" placeholder="Senha" required><br><br>
            <button type="submit">Entrar</button>
        </form>
    """)

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

# Dashboard do Usuário exibindo o seu link de afiliado exclusivo
@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE username = ?', (session['username'],)).fetchone()
    conn.close()
    
    if not user:
        return redirect(url_for('logout'))
        
    affiliate_link = f"{request.host_url}ref/{user['affiliate_code']}"
    
    return render_template_string("""
        <h2>Bem-vindo, {{ user['username'] }}</h2>
        <p>Seu link de afiliado exclusivo:</p>
        <input type="text" value="{{ link }}" readonly style="width: 400px; padding: 5px;">
        <br><br>
        <a href="/logout">Sair</a>
    """, user=user, link=affiliate_link)

# Rota para processar o depósito salvando vinculado ao afiliado da sessão
@app.route('/depositar', methods=['POST'])
def depositar():
    if 'username' not in session:
        return redirect(url_for('login'))
        
    username = session['username']
    amount = float(request.form.get('amount', 0))
    
    # Pega o código de afiliado armazenado na sessão (se acessou via link de alguém)
    affiliate_code = session.get('ref_code', 'direto')
    
    conn = get_db_connection()
    conn.execute(
        'INSERT INTO affiliate_deposits (affiliate_code, username, amount) VALUES (?, ?, ?)',
        (affiliate_code, username, amount)
    )
    conn.commit()
    conn.close()
    
    return "Depósito efetuado com sucesso e computado no sistema de afiliados!"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
