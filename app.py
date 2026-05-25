import streamlit as st
import pandas as pd
import datetime
import plotly.express as px
from db import init_db, get_categories, add_transaction, get_transactions, get_summary, get_expenses_by_category, get_incomes_by_category, delete_transaction, update_transaction, update_category_limit

# Настройка страницы
st.set_page_config(page_title="Личные Финансы", page_icon="💸", layout="wide")

# Кастомные стили с учетом UX-аудита
st.markdown("""
    <style>
    .metric-card {
        background-color: #2b2b36;
        border-radius: 10px;
        padding: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.4);
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
        font-size: clamp(20px, 4vw, 28px);
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

@st.cache_resource
def setup_database():
    init_db()
    return True

setup_database()

# --- Боковая панель ---
with st.sidebar:
    st.header("Управление и Настройки")
    
    st.subheader("➕ Добавить операцию")
    with st.expander("Заполнить форму", expanded=True):
        t_type = st.radio("Тип операции", ["расход", "доход"], horizontal=True, key="t_type_radio")
        
        categories_df = get_categories(t_type)
        category_options = dict(zip(categories_df['name'], categories_df['id']))
        
        selected_category_name = st.selectbox("Категория", list(category_options.keys()))
        amount = st.number_input("Сумма (₽)", min_value=0.01, step=100.0)
        date = st.date_input("Дата", datetime.date.today())
        description = st.text_input("Описание (необязательно)")
        
        if st.button("Добавить", type="primary", use_container_width=True):
            cat_id = category_options[selected_category_name]
            add_transaction(amount, cat_id, date, description, t_type)
            st.success("Успешно добавлено!")
            st.rerun()

    st.divider()

    st.subheader("📅 Период аналитики")
    # Единый виджет для периода
    today = datetime.date.today()
    first_day = today.replace(day=1)
    dates = st.date_input("Выберите диапазон дат", value=(first_day, today), key="date_range")
    
    if isinstance(dates, tuple) and len(dates) == 2:
        start_date, end_date = dates
    else:
        start_date, end_date = first_day, today

st.title("💸 Мой Бюджет")

# --- KPI Карточки ---
balance, income_period, expense_period = get_summary(start_date, end_date)

col1, col2, col3 = st.columns(3)
with col1:
    st.markdown(f"""
        <div class="metric-card balance">
            <div class="metric-label">Баланс (всё время)</div>
            <div class="metric-value" style="color: #2196F3;">{balance:,.2f} ₽</div>
        </div>
    """, unsafe_allow_html=True)
with col2:
    st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Доходы (период)</div>
            <div class="metric-value" style="color: #4CAF50;">{income_period:,.2f} ₽</div>
        </div>
    """, unsafe_allow_html=True)
with col3:
    st.markdown(f"""
        <div class="metric-card expense">
            <div class="metric-label">Расходы (период)</div>
            <div class="metric-value" style="color: #FF5252;">{expense_period:,.2f} ₽</div>
        </div>
    """, unsafe_allow_html=True)

st.divider()

# --- Аналитика и Управление ---
tab_analytics, tab_limits, tab_history = st.tabs(["📊 Аналитика", "🎯 Лимиты и Бюджеты", "📜 История операций"])

with tab_analytics:
    expenses_df = get_expenses_by_category(start_date, end_date)
    incomes_df = get_incomes_by_category(start_date, end_date)
    
    col_exp_chart, col_inc_chart = st.columns(2)
    
    with col_exp_chart:
        if not expenses_df.empty:
            # Горизонтальный Bar Chart
            fig = px.bar(
                expenses_df.sort_values('total', ascending=True), 
                x='total', 
                y='category', 
                orientation='h',
                title='Структура расходов',
                color_discrete_sequence=['#FF5252']
            )
            fig.update_layout(margin=dict(t=40, b=0, l=0, r=0), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Нет расходов.")

    with col_inc_chart:
        if not incomes_df.empty:
            fig_inc = px.bar(
                incomes_df.sort_values('total', ascending=True), 
                x='total', 
                y='category', 
                orientation='h',
                title='Структура доходов',
                color_discrete_sequence=['#4CAF50']
            )
            fig_inc.update_layout(margin=dict(t=40, b=0, l=0, r=0), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_inc, use_container_width=True)
        else:
            st.info("Нет доходов.")

with tab_limits:
    st.subheader("Статус бюджетов")
    expenses_df = get_expenses_by_category(start_date, end_date)
    
    if not expenses_df.empty:
        for idx, row in expenses_df.iterrows():
            limit = row.get('monthly_limit', 0)
            if limit > 0:
                total = row['total']
                progress = min(total / limit, 1.0)
                st.progress(progress, text=f"{row['category']}: {total:,.0f} ₽ из {limit:,.0f} ₽")
    else:
        st.write("Добавьте расходы, чтобы увидеть статус.")
        
    st.divider()
    st.subheader("Редактирование лимитов")
    cats_exp = get_categories('расход')
    if not cats_exp.empty:
        edited_limits = st.data_editor(
            cats_exp[['id', 'name', 'monthly_limit']],
            column_config={
                "id": None,
                "name": st.column_config.TextColumn("Категория", disabled=True),
                "monthly_limit": st.column_config.NumberColumn("Лимит в месяц (₽)", min_value=0.0, step=1000.0, format="%.2f")
            },
            hide_index=True,
            use_container_width=True,
            key="limits_table_editor"
        )
        if st.button("💾 Сохранить изменения лимитов"):
            for idx, row in edited_limits.iterrows():
                update_category_limit(int(row['id']), float(row['monthly_limit']))
            st.success("Лимиты обновлены!")
            st.rerun()

with tab_history:
    col_title, col_export = st.columns([3, 1])
    with col_export:
        transactions_df = get_transactions(start_date, end_date)
        if not transactions_df.empty:
            export_df = transactions_df.copy()
            export_df['description'] = export_df['description'].apply(
                lambda x: f"'{x}" if isinstance(x, str) and str(x).startswith(('=', '+', '-', '@')) else x
            )
            csv_data = export_df[['date', 'type', 'category', 'amount', 'description']].rename(columns={
                'date': 'Дата',
                'type': 'Тип',
                'category': 'Категория',
                'amount': 'Сумма',
                'description': 'Описание'
            }).to_csv(index=False).encode('utf-8')
            st.download_button("📥 Скачать CSV", data=csv_data, file_name='transactions_history.csv', mime='text/csv')

    if not transactions_df.empty:
        st.write("Вы можете выделять строки и нажимать `Delete` на клавиатуре, чтобы удалять операции. После этого нажмите кнопку сохранения.")
        
        # Подготавливаем dataframe для editor
        editor_df = transactions_df.copy()
        editor_df['amount'] = editor_df.apply(lambda r: r['amount'] if r['type'] == 'расход' else r['amount'], axis=1)
        
        # Интерактивная таблица с возможностью удаления строк
        edited_history = st.data_editor(
            editor_df[['id', 'date', 'type', 'category', 'amount', 'description']],
            column_config={
                "id": None, # Скрываем ID
                "date": st.column_config.DateColumn("Дата", disabled=True),
                "type": st.column_config.TextColumn("Тип", disabled=True),
                "category": st.column_config.TextColumn("Категория", disabled=True),
                "amount": st.column_config.NumberColumn("Сумма", format="%.2f", disabled=True),
                "description": st.column_config.TextColumn("Описание", disabled=True)
            },
            hide_index=True,
            num_rows="dynamic",
            use_container_width=True,
            key="history_editor"
        )
        
        # Логика удаления
        if st.button("💾 Применить удаления", type="primary"):
            # Ищем, какие ID пропали
            original_ids = set(transactions_df['id'])
            remaining_ids = set(edited_history['id'].dropna())
            deleted_ids = original_ids - remaining_ids
            
            if deleted_ids:
                for tx_id in deleted_ids:
                    delete_transaction(int(tx_id))
                st.success(f"Удалено операций: {len(deleted_ids)}")
                st.rerun()
            else:
                st.info("Изменений нет.")
    else:
        st.info("История пуста.")
