def init_db():
    conn = get_db_connection()
    # Tabela de usuários (adicionando campo para afiliado/código único se não existir)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            is_admin INTEGER DEFAULT 0,
            affiliate_code TEXT UNIQUE
        )
    ''')
    
    # Tabela para registrar cada depósito feito através de um link de afiliado
    conn.execute('''
        CREATE TABLE IF NOT EXISTS affiliate_deposits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            affiliate_code TEXT NOT NULL,
            username TEXT NOT NULL,
            amount REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

# Chame init_db() logo após instanciar o app
init_db()
