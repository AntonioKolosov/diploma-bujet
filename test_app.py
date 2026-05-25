import pytest
import os
from db import get_connection, init_db, create_user, add_transaction, get_categories, get_summary

# Переопределяем DB_FILE для тестов, чтобы не портить основную базу
os.environ['TESTING'] = '1'
import db
db.DB_FILE = 'test_finance.duckdb'

@pytest.fixture(autouse=True)
def setup_teardown():
    # Setup
    if os.path.exists(db.DB_FILE):
        os.remove(db.DB_FILE)
    init_db()
    
    yield
    
    # Teardown
    if os.path.exists(db.DB_FILE):
        os.remove(db.DB_FILE)
    try:
        if os.path.exists(db.DB_FILE + '.wal'):
            os.remove(db.DB_FILE + '.wal')
    except:
        pass

def test_initial_categories():
    user_id, group_id, err = create_user("test_user", "password123")
    categories = get_categories(group_id)
    assert len(categories) > 0
    assert 'Зарплата' in categories['name'].values
    assert 'Продукты' in categories['name'].values

def test_add_transaction_and_balance():
    user_id, group_id, err = create_user("test_user_2", "password123")
    
    # Получаем ID категории
    categories = get_categories(group_id, 'доход')
    income_cat_id = int(categories.iloc[0]['id'])
    
    categories_exp = get_categories(group_id, 'расход')
    expense_cat_id = int(categories_exp.iloc[0]['id'])
    
    # Добавляем доход
    add_transaction(group_id, 1000.0, income_cat_id, '2023-01-01', 'Test Income', 'доход')
    
    # Проверяем баланс
    balance, inc, exp = get_summary(group_id)
    assert balance == 1000.0
    
    # Добавляем расход
    add_transaction(group_id, 250.0, expense_cat_id, '2023-01-02', 'Test Expense', 'расход')
    
    balance, inc, exp = get_summary(group_id)
    assert balance == 750.0
