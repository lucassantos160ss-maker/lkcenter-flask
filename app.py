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
    
    # Garante compatibilidade caso o banco antigo já exista sem as colunas novas
    cursor.execute("PRAGMA table_info(usuarios)")
    colunas = [col['name'] for col in cursor.fetchall()]
    if 'codigo_convite' not in colunas:
        cursor.execute("ALTER TABLE usuarios ADD COLUMN codigo_convite TEXT UNIQUE")
    if 'pontos' not in colunas:
        cursor.execute("ALTER TABLE usuarios ADD COLUMN pontos INTEGER DEFAULT 0")
    if 'nivel_pontos' not in colunas:
        cursor.execute("ALTER TABLE usuarios ADD COLUMN nivel_pontos INTEGER DEFAULT 1")
    if 'bonus_pendente_afiliado' not in colunas:
        cursor.execute("ALTER TABLE usuarios ADD COLUMN bonus_pendente_afiliado REAL DEFAULT 0.00")

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
    
    # Criar admin padrão
    cursor.execute("SELECT * FROM usuarios WHERE username = 'S.lucas1'")
    user_lucas = cursor.fetchone()
    if not user_lucas:
        cursor.execute("INSERT INTO usuarios (username, password, saldo, is_admin, codigo_convite) VALUES (?, ?, ?, ?, ?)",
                       ('S.lucas1', generate_password_hash('admin123'), 0.00, 1, 'LK777'))
    else:
        cursor.execute("UPDATE usuarios SET is_admin = 1, codigo_convite = COALESCE(codigo_convite, 'LK777') WHERE username = 'S.lucas1'")

    # Inserir bins iniciais padrão
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

# Inicializa o banco ao carregar o app no Render
init_db()

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM usuarios WHERE username = ?", (username,)).fetchone()
        conn.close()
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['is_admin'] = user['is_admin']
            return redirect(url_for('dashboard'))
        else:
            return "Usuário ou senha incorretos! <a href='/'>Voltar</a>"
            
    return """
    <html>
    <head><title>Login - Center do Pecinha</title></head>
    <body style="background:#121214; color:#fff; font-family:sans-serif; display:flex; justify-content:center; align-items:center; height:100vh;">
        <div style="background:#18181b; padding:30px; border-radius:12px; border:1px solid #333; width:300px;">
            <h2 style="text-align:center;">CENTER DO PECINHA</h2>
            <form method="POST">
                <label>Usuário</label><br>
                <input type="text" name="username" required style="width:100%; padding:8px; margin:8px 0 15px 0; background:#09090b; border:1px solid #444; color:#fff;"><br>
                <label>Senha</label><br>
                <input type="password" name="password" required style="width:100%; padding:8px; margin:8px 0 20px 0; background:#09090b; border:1px solid #444; color:#fff;"><br>
                <button type="submit" style="width:100%; padding:10px; background:#22c55e; border:none; color:#fff; font-weight:bold; cursor:pointer;">Entrar</button>
            </form>
        </div>
    </body>
    </html>
    """

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return f"Bem-vindo ao Dashboard, {session['username']}! <a href='/logout'>Sair</a>"

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
