import duckdb
import datetime
import pandas as pd

DB_FILE = 'finance.duckdb'

def get_connection():
    return duckdb.connect(DB_FILE)

def init_db():
    conn = get_connection()
    
    # Создание таблицы категорий
    conn.execute("""
        CREATE SEQUENCE IF NOT EXISTS seq_category_id;
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER DEFAULT nextval('seq_category_id') PRIMARY KEY,
            name VARCHAR NOT NULL,
            type VARCHAR NOT NULL CHECK (type IN ('доход', 'расход'))
        );
    """)
    
    # Создание таблицы транзакций
    conn.execute("""
        CREATE SEQUENCE IF NOT EXISTS seq_transaction_id;
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER DEFAULT nextval('seq_transaction_id') PRIMARY KEY,
            amount DECIMAL(10, 2) NOT NULL,
            category_id INTEGER,
            date DATE NOT NULL,
            description VARCHAR,
            type VARCHAR NOT NULL CHECK (type IN ('доход', 'расход')),
            FOREIGN KEY (category_id) REFERENCES categories(id)
        );
    """)
    
    # Добавление колонки лимитов, если её нет
    info = conn.execute("PRAGMA table_info('categories')").df()
    if 'monthly_limit' not in info['name'].values:
        conn.execute("ALTER TABLE categories ADD COLUMN monthly_limit DECIMAL(10, 2) DEFAULT 0.0")
        
    # Добавление базовых категорий, если их нет
    count = conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
    if count == 0:
        base_categories = [
            ('Зарплата', 'доход'),
            ('Подработки', 'доход'),
            ('Подарки', 'доход'),
            ('Инвестиции', 'доход'),
            ('Продукты', 'расход'),
            ('Транспорт', 'расход'),
            ('Жилье', 'расход'),
            ('Развлечения', 'расход'),
            ('Здоровье', 'расход'),
            ('Одежда', 'расход'),
            ('Прочее', 'расход')
        ]
        conn.executemany("INSERT INTO categories (name, type) VALUES (?, ?)", base_categories)
        
    conn.close()

def get_categories(type_filter=None):
    conn = get_connection()
    if type_filter:
        df = conn.execute("SELECT * FROM categories WHERE type = ?", [type_filter]).df()
    else:
        df = conn.execute("SELECT * FROM categories").df()
    conn.close()
    return df

def add_transaction(amount, category_id, date, description, t_type):
    conn = get_connection()
    conn.execute("""
        INSERT INTO transactions (amount, category_id, date, description, type)
        VALUES (?, ?, ?, ?, ?)
    """, [amount, category_id, date, description, t_type])
    conn.close()

def update_transaction(t_id, amount, category_id, date, description, t_type):
    conn = get_connection()
    conn.execute("""
        UPDATE transactions 
        SET amount=?, category_id=?, date=?, description=?, type=?
        WHERE id=?
    """, [amount, category_id, date, description, t_type, t_id])
    conn.close()

def delete_transaction(t_id):
    conn = get_connection()
    conn.execute("DELETE FROM transactions WHERE id=?", [t_id])
    conn.close()

def update_category_limit(category_id, limit):
    conn = get_connection()
    conn.execute("UPDATE categories SET monthly_limit=? WHERE id=?", [limit, category_id])
    conn.close()

def get_transactions(start_date=None, end_date=None):
    conn = get_connection()
    query = """
        SELECT t.id, t.amount, c.name as category, t.date, t.description, t.type
        FROM transactions t
        LEFT JOIN categories c ON t.category_id = c.id
    """
    params = []
    
    if start_date and end_date:
        query += " WHERE t.date >= ? AND t.date <= ?"
        params.extend([start_date, end_date])
        
    query += " ORDER BY t.date DESC"
    df = conn.execute(query, params).df()
    conn.close()
    return df

def get_summary(start_date=None, end_date=None):
    conn = get_connection()
    
    # Общий баланс (за всё время)
    balance_query = """
        SELECT 
            COALESCE(SUM(CASE WHEN type = 'доход' THEN amount ELSE 0 END), 0) - 
            COALESCE(SUM(CASE WHEN type = 'расход' THEN amount ELSE 0 END), 0)
        FROM transactions
    """
    balance = conn.execute(balance_query).fetchone()[0] or 0.0
    
    # Доходы и расходы за выбранный период
    monthly_query = """
        SELECT 
            type, COALESCE(SUM(amount), 0) as total
        FROM transactions
    """
    params = []
    if start_date and end_date:
        monthly_query += " WHERE date >= ? AND date <= ?"
        params.extend([start_date, end_date])
        
    monthly_query += " GROUP BY type"
    
    monthly_stats = conn.execute(monthly_query, params).fetchall()
    
    income_period = 0.0
    expense_period = 0.0
    for row in monthly_stats:
        if row[0] == 'доход':
            income_period = row[1]
        else:
            expense_period = row[1]
            
    conn.close()
    return balance, income_period, expense_period

def get_expenses_by_category(start_date=None, end_date=None):
    conn = get_connection()
    query = """
        SELECT c.id, c.name as category, SUM(t.amount) as total, c.monthly_limit
        FROM transactions t
        JOIN categories c ON t.category_id = c.id
        WHERE t.type = 'расход'
    """
    params = []
    if start_date and end_date:
        query += " AND t.date >= ? AND t.date <= ?"
        params.extend([start_date, end_date])
        
    query += " GROUP BY c.id, c.name, c.monthly_limit ORDER BY total DESC"
    df = conn.execute(query, params).df()
    conn.close()
    return df

def get_incomes_by_category(start_date=None, end_date=None):
    conn = get_connection()
    query = """
        SELECT c.name as category, SUM(t.amount) as total
        FROM transactions t
        JOIN categories c ON t.category_id = c.id
        WHERE t.type = 'доход'
    """
    params = []
    if start_date and end_date:
        query += " AND t.date >= ? AND t.date <= ?"
        params.extend([start_date, end_date])
        
    query += " GROUP BY c.name ORDER BY total DESC"
    df = conn.execute(query, params).df()
    conn.close()
    return df
