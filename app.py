from flask import Flask, render_template, request, redirect, session
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'sua_chave_secreta_aqui'

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    # Tabela de usuários
    conn.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    
    # Tabela de bins/categorias de estoque
    conn.execute('''
        CREATE TABLE IF NOT EXISTS bins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL
        )
    ''')
    
    # Tabela de estoque/conteúdos
    conn.execute('''
        CREATE TABLE IF NOT EXISTS estoque (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bin_id INTEGER,
            conteudo TEXT NOT NULL,
            status TEXT DEFAULT 'disponivel',
            FOREIGN KEY (bin_id) REFERENCES bins (id)
        )
    ''')
    
    # Criar usuário admin padrão se não existir (username: S.lucas1)
    admin_user = conn.execute('SELECT * FROM usuarios WHERE username = ?', ('S.lucas1',)).fetchone()
    if not admin_user:
        hashed_password = generate_password_hash('sua_senha_aqui')
        conn.execute('INSERT INTO usuarios (username, password) VALUES (?, ?)', ('S.lucas1', hashed_password))
    
    conn.commit()
    conn.close()

# Executa a criação do banco automaticamente assim que o app sobe no Render/Gunicorn
init_db()

def get_user_logged():
    if 'user_id' in session:
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM usuarios WHERE id = ?', (session['user_id'],)).fetchone()
        conn.close()
        return user
    return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM usuarios WHERE username = ?', (username,)).fetchone()
        conn.close()
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            if user['username'] == 'S.lucas1':
                return redirect('/admin_secret_lk')
            return redirect('/')
        return "Credenciais inválidas", 401
        
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect('/login')

@app.route('/admin_secret_lk')
def admin_painel():
    user = get_user_logged()
    if not user or user['username'] != 'S.lucas1':
        return "Acesso Negado", 403
        
    conn = get_db_connection()
    bins = conn.execute('SELECT * FROM bins').fetchall()
    conn.close()
    
    return render_template('admin.html', bins=bins)

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
        for linha in linhas:
            conteudo = linha.strip()
            if conteudo:
                conn.execute("INSERT INTO estoque (bin_id, conteudo, status) VALUES (?, ?, 'disponivel')", (bin_id, conteudo))
        conn.commit()
        conn.close()
        
    return redirect('/admin_secret_lk?msg=Estoque+abastecido+com+sucesso!')

if __name__ == '__main__':
    app.run(debug=True)
