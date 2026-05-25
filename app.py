import streamlit as st
import pandas as pd
import datetime
import plotly.express as px
from db import init_db, get_categories, add_transaction, get_transactions, get_summary, get_expenses_by_category, delete_transaction, update_transaction, update_category_limit

# Настройка страницы
st.set_page_config(page_title="Личные Финансы", page_icon="💸", layout="wide")

# Кастомные стили
st.markdown("""
    <style>
    .metric-card {
        background-color: #1e1e24;
        border-radius: 10px;
        padding: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        text-align: center;
        margin-bottom: 20px;
        border-top: 4px solid #4CAF50;
    }
    .metric-card.expense {
        border-top: 4px solid #FF5252;
    }
    .metric-card.balance {
        border-top: 4px solid #2196F3;
    }
    .metric-value {
        font-size: 28px;
        font-weight: bold;
        margin: 10px 0;
    }
    .metric-label {
        font-size: 14px;
        color: #9e9e9e;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    </style>
""", unsafe_allow_html=True)

init_db()

# Боковая панель для фильтров и лимитов
with st.sidebar:
    st.header("Настройки и Фильтры")
    
    st.subheader("📅 Период")
    start_date = st.date_input("Начало", datetime.date.today().replace(day=1))
    end_date = st.date_input("Конец", datetime.date.today())
    
    st.divider()
    
    st.subheader("🎯 Лимиты категорий")
    categories_df_exp = get_categories('расход')
    if not categories_df_exp.empty:
        cat_to_limit = st.selectbox("Категория для лимита", categories_df_exp['name'].tolist())
        cat_id_limit = categories_df_exp[categories_df_exp['name'] == cat_to_limit].iloc[0]['id']
        current_limit = categories_df_exp[categories_df_exp['name'] == cat_to_limit].iloc[0].get('monthly_limit', 0.0)
        
        new_limit = st.number_input("Новый лимит (₽)", min_value=0.0, value=float(current_limit), step=1000.0)
        if st.button("Обновить лимит"):
            update_category_limit(int(cat_id_limit), new_limit)
            st.success("Лимит обновлен!")
            st.rerun()

st.title("💸 Мой Бюджет")

# --- KPI Карточки ---
balance, income_period, expense_period = get_summary(start_date, end_date)

col1, col2, col3 = st.columns(3)
with col1:
    st.markdown(f"""
        <div class="metric-card balance">
            <div class="metric-label">Баланс (за всё время)</div>
            <div class="metric-value" style="color: #2196F3;">{balance:,.2f} ₽</div>
        </div>
    """, unsafe_allow_html=True)
with col2:
    st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Доходы (за период)</div>
            <div class="metric-value" style="color: #4CAF50;">{income_period:,.2f} ₽</div>
        </div>
    """, unsafe_allow_html=True)
with col3:
    st.markdown(f"""
        <div class="metric-card expense">
            <div class="metric-label">Расходы (за период)</div>
            <div class="metric-value" style="color: #FF5252;">{expense_period:,.2f} ₽</div>
        </div>
    """, unsafe_allow_html=True)

st.divider()

# --- Основной контент ---
col_form, col_charts = st.columns([1, 2])

with col_form:
    st.subheader("➕ Добавить операцию")
    t_type = st.radio("Тип операции", ["расход", "доход"], horizontal=True, key="t_type_radio")
    
    categories_df = get_categories(t_type)
    category_options = dict(zip(categories_df['name'], categories_df['id']))
    
    selected_category_name = st.selectbox("Категория", list(category_options.keys()))
    amount = st.number_input("Сумма (₽)", min_value=0.01, step=100.0)
    date = st.date_input("Дата", datetime.date.today())
    description = st.text_input("Описание (необязательно)")
    
    if st.button("Добавить", type="primary"):
        cat_id = category_options[selected_category_name]
        add_transaction(amount, cat_id, date, description, t_type)
        st.success("Операция успешно добавлена!")
        st.rerun()

with col_charts:
    st.subheader("📊 Аналитика и Бюджеты")
    expenses_df = get_expenses_by_category(start_date, end_date)
    
    if not expenses_df.empty:
        fig = px.pie(
            expenses_df, 
            values='total', 
            names='category', 
            title='Структура расходов',
            hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        fig.update_traces(textposition='inside', textinfo='percent+label')
        fig.update_layout(margin=dict(t=40, b=0, l=0, r=0), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True) # or width='stretch' if streamlit supports it without warning
        
        # Показ лимитов
        st.write("**Статус бюджетов (Лимиты)**")
        for idx, row in expenses_df.iterrows():
            limit = row.get('monthly_limit', 0)
            if limit > 0:
                total = row['total']
                progress = min(total / limit, 1.0)
                color = "normal" if progress < 0.9 else "error"
                st.progress(progress, text=f"{row['category']}: {total:,.0f} ₽ из {limit:,.0f} ₽")
    else:
        st.info("Нет данных о расходах за выбранный период.")

st.divider()

# --- История транзакций и управление ---
st.subheader("📜 Управление операциями")
transactions_df = get_transactions(start_date, end_date)

if not transactions_df.empty:
    display_df = transactions_df.copy()
    display_df['Сумма_str'] = display_df.apply(
        lambda row: f"+{row['amount']:.2f}" if row['type'] == 'доход' else f"-{row['amount']:.2f}", axis=1
    )
    
    # UI для редактирования и удаления
    with st.expander("Редактировать / Удалить операцию", expanded=False):
        tx_options = [f"ID: {row['id']} | {row['date']} | {row['category']} | {row['Сумма_str']} | {row['description'] or ''}" for idx, row in display_df.iterrows()]
        selected_tx_str = st.selectbox("Выберите операцию", tx_options)
        
        if selected_tx_str:
            tx_id = int(selected_tx_str.split(" | ")[0].replace("ID: ", ""))
            tx_row = transactions_df[transactions_df['id'] == tx_id].iloc[0]
            
            action = st.radio("Действие", ["Редактировать", "Удалить"], horizontal=True)
            
            if action == "Удалить":
                if st.button("🗑 Удалить безвозвратно", type="primary"):
                    delete_transaction(tx_id)
                    st.success("Удалено!")
                    st.rerun()
            elif action == "Редактировать":
                with st.form(f"edit_form_{tx_id}"):
                    e_type = st.radio("Тип", ["расход", "доход"], index=0 if tx_row['type'] == 'расход' else 1)
                    e_cats = get_categories(e_type)
                    e_cat_options = dict(zip(e_cats['name'], e_cats['id']))
                    
                    e_cat_name = tx_row['category'] if tx_row['category'] in e_cat_options else list(e_cat_options.keys())[0]
                    e_selected_cat = st.selectbox("Категория", list(e_cat_options.keys()), index=list(e_cat_options.keys()).index(e_cat_name))
                    e_amount = st.number_input("Сумма (₽)", min_value=0.01, value=float(tx_row['amount']))
                    e_date = st.date_input("Дата", tx_row['date'])
                    e_desc = st.text_input("Описание", value=tx_row['description'] if tx_row['description'] else "")
                    
                    if st.form_submit_button("💾 Сохранить изменения"):
                        update_transaction(tx_id, e_amount, e_cat_options[e_selected_cat], e_date, e_desc, e_type)
                        st.success("Обновлено!")
                        st.rerun()

    # Таблица истории
    st.dataframe(
        display_df[['date', 'type', 'category', 'Сумма_str', 'description']].rename(columns={
            'date': 'Дата',
            'type': 'Тип',
            'category': 'Категория',
            'Сумма_str': 'Сумма',
            'description': 'Описание'
        }),
        use_container_width=True,
        hide_index=True
    )
else:
    st.info("История операций пуста за этот период.")
