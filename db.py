import duckdb
import bcrypt
import secrets
import string

DB_FILE = 'finance.duckdb'

def get_connection():
    return duckdb.connect(DB_FILE)

def init_db():
    with get_connection() as conn:
        conn.execute("""
            CREATE SEQUENCE IF NOT EXISTS seq_group_id;
            CREATE TABLE IF NOT EXISTS groups (
                id INTEGER DEFAULT nextval('seq_group_id') PRIMARY KEY,
                invite_code VARCHAR UNIQUE NOT NULL
            );
        """)
        
        conn.execute("""
            CREATE SEQUENCE IF NOT EXISTS seq_user_id;
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER DEFAULT nextval('seq_user_id') PRIMARY KEY,
                username VARCHAR UNIQUE NOT NULL,
                password_hash VARCHAR NOT NULL,
                group_id INTEGER NOT NULL,
                FOREIGN KEY (group_id) REFERENCES groups(id)
            );
        """)
        
        conn.execute("""
            CREATE SEQUENCE IF NOT EXISTS seq_category_id;
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER DEFAULT nextval('seq_category_id') PRIMARY KEY,
                group_id INTEGER NOT NULL,
                name VARCHAR NOT NULL,
                type VARCHAR NOT NULL CHECK (type IN ('доход', 'расход')),
                monthly_limit DECIMAL(10, 2) DEFAULT 0.0,
                FOREIGN KEY (group_id) REFERENCES groups(id)
            );
        """)
        
        conn.execute("""
            CREATE SEQUENCE IF NOT EXISTS seq_transaction_id;
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER DEFAULT nextval('seq_transaction_id') PRIMARY KEY,
                group_id INTEGER NOT NULL,
                amount DECIMAL(10, 2) NOT NULL CHECK (amount > 0),
                category_id INTEGER,
                date DATE NOT NULL,
                description VARCHAR,
                type VARCHAR NOT NULL CHECK (type IN ('доход', 'расход')),
                FOREIGN KEY (group_id) REFERENCES groups(id),
                FOREIGN KEY (category_id) REFERENCES categories(id)
            );
        """)

def generate_invite_code(length=8):
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def create_user(username, password, invite_code=None):
    with get_connection() as conn:
        exists = conn.execute("SELECT id FROM users WHERE username=?", [username]).fetchone()
        if exists:
            return None, None, "Пользователь с таким логином уже существует."
            
        group_id = None
        if invite_code:
            # Join existing group
            group_row = conn.execute("SELECT id FROM groups WHERE invite_code=?", [invite_code]).fetchone()
            if not group_row:
                return None, None, "Группа с таким кодом не найдена. Оставьте поле пустым для создания новой группы."
            group_id = group_row[0]
            
        if not group_id:
            # Create new group
            new_code = generate_invite_code()
            conn.execute("INSERT INTO groups (invite_code) VALUES (?)", [new_code])
            group_id = conn.execute("SELECT id FROM groups WHERE invite_code=?", [new_code]).fetchone()[0]
            
            # Initialize default categories for new group
            base_categories = [
                (group_id, 'Зарплата', 'доход'), (group_id, 'Подработки', 'доход'), (group_id, 'Подарки', 'доход'),
                (group_id, 'Инвестиции', 'доход'), (group_id, 'Продукты', 'расход'), (group_id, 'Транспорт', 'расход'),
                (group_id, 'Жилье', 'расход'), (group_id, 'Развлечения', 'расход'), (group_id, 'Здоровье', 'расход'),
                (group_id, 'Одежда', 'расход'), (group_id, 'Прочее', 'расход')
            ]
            conn.executemany("INSERT INTO categories (group_id, name, type) VALUES (?, ?, ?)", base_categories)

        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        conn.execute("INSERT INTO users (username, password_hash, group_id) VALUES (?, ?, ?)", [username, hashed, group_id])
        user_id = conn.execute("SELECT id FROM users WHERE username=?", [username]).fetchone()[0]
        
        return user_id, group_id, None

def verify_user(username, password):
    with get_connection() as conn:
        row = conn.execute("SELECT id, password_hash, group_id FROM users WHERE username=?", [username]).fetchone()
        if row:
            user_id, pwd_hash, group_id = row
            if bcrypt.checkpw(password.encode('utf-8'), pwd_hash.encode('utf-8')):
                return user_id, group_id
        return None, None

def get_invite_code(group_id):
    with get_connection() as conn:
        row = conn.execute("SELECT invite_code FROM groups WHERE id=?", [group_id]).fetchone()
        return row[0] if row else None

# Data operations (using group_id instead of user_id)
def get_categories(group_id, type_filter=None):
    with get_connection() as conn:
        if type_filter:
            df = conn.execute("SELECT * FROM categories WHERE group_id = ? AND type = ?", [group_id, type_filter]).df()
        else:
            df = conn.execute("SELECT * FROM categories WHERE group_id = ?", [group_id]).df()
        return df

def add_transaction(group_id, amount, category_id, date, description, t_type):
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO transactions (group_id, amount, category_id, date, description, type)
            VALUES (?, ?, ?, ?, ?, ?)
        """, [group_id, amount, category_id, date, description, t_type])

def update_transaction(group_id, t_id, amount, category_id, date, description, t_type):
    with get_connection() as conn:
        conn.execute("""
            UPDATE transactions 
            SET amount=?, category_id=?, date=?, description=?, type=?
            WHERE id=? AND group_id=?
        """, [amount, category_id, date, description, t_type, t_id, group_id])

def delete_transaction(group_id, t_id):
    with get_connection() as conn:
        conn.execute("DELETE FROM transactions WHERE id=? AND group_id=?", [t_id, group_id])

def update_category_limit(group_id, category_id, limit):
    with get_connection() as conn:
        conn.execute("UPDATE categories SET monthly_limit=? WHERE id=? AND group_id=?", [limit, category_id, group_id])

def get_transactions(group_id, start_date=None, end_date=None):
    with get_connection() as conn:
        query = """
            SELECT t.id, t.amount, c.name as category, t.date, t.description, t.type
            FROM transactions t
            LEFT JOIN categories c ON t.category_id = c.id
            WHERE t.group_id = ?
        """
        params = [group_id]
        
        if start_date and end_date:
            query += " AND t.date >= ? AND t.date <= ?"
            params.extend([start_date, end_date])
            
        query += " ORDER BY t.date DESC"
        df = conn.execute(query, params).df()
        return df

def get_summary(group_id, start_date=None, end_date=None):
    with get_connection() as conn:
        balance_query = """
            SELECT 
                COALESCE(SUM(CASE WHEN type = 'доход' THEN amount ELSE 0 END), 0) - 
                COALESCE(SUM(CASE WHEN type = 'расход' THEN amount ELSE 0 END), 0)
            FROM transactions
            WHERE group_id = ?
        """
        balance = conn.execute(balance_query, [group_id]).fetchone()[0] or 0.0
        
        monthly_query = """
            SELECT 
                type, COALESCE(SUM(amount), 0) as total
            FROM transactions
            WHERE group_id = ?
        """
        params = [group_id]
        if start_date and end_date:
            monthly_query += " AND date >= ? AND date <= ?"
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
                
        return balance, income_period, expense_period

def get_expenses_by_category(group_id, start_date=None, end_date=None):
    with get_connection() as conn:
        query = """
            SELECT c.id, c.name as category, SUM(t.amount) as total, c.monthly_limit
            FROM transactions t
            JOIN categories c ON t.category_id = c.id
            WHERE t.group_id = ? AND t.type = 'расход'
        """
        params = [group_id]
        if start_date and end_date:
            query += " AND t.date >= ? AND t.date <= ?"
            params.extend([start_date, end_date])
            
        query += " GROUP BY c.id, c.name, c.monthly_limit ORDER BY total DESC"
        df = conn.execute(query, params).df()
        return df

def get_incomes_by_category(group_id, start_date=None, end_date=None):
    with get_connection() as conn:
        query = """
            SELECT c.name as category, SUM(t.amount) as total
            FROM transactions t
            JOIN categories c ON t.category_id = c.id
            WHERE t.group_id = ? AND t.type = 'доход'
        """
        params = [group_id]
        if start_date and end_date:
            query += " AND t.date >= ? AND t.date <= ?"
            params.extend([start_date, end_date])
            
        query += " GROUP BY c.name ORDER BY total DESC"
        df = conn.execute(query, params).df()
        return df
