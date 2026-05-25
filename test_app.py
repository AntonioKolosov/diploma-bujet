import pytest
import os
from db import get_connection, init_db, add_transaction, get_categories, get_summary

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
    categories = get_categories()
    assert len(categories) > 0
    assert 'Зарплата' in categories['name'].values
    assert 'Продукты' in categories['name'].values

def test_add_transaction_and_balance():
    # Получаем ID категории
    categories = get_categories('доход')
    income_cat_id = int(categories.iloc[0]['id'])
    
    categories_exp = get_categories('расход')
    expense_cat_id = int(categories_exp.iloc[0]['id'])
    
    # Добавляем доход
    add_transaction(1000.0, income_cat_id, '2023-01-01', 'Test Income', 'доход')
    
    # Проверяем баланс
    balance, inc, exp = get_summary()
    assert balance == 1000.0
    
    # Добавляем расход
    add_transaction(250.0, expense_cat_id, '2023-01-02', 'Test Expense', 'расход')
    
    balance, inc, exp = get_summary()
    assert balance == 750.0
