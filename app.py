import streamlit as st
import pandas as pd
import datetime
import plotly.express as px
from db import (
    init_db, create_user, verify_user, get_invite_code,
    get_categories, add_transaction, get_transactions, 
    get_summary, get_expenses_by_category, get_incomes_by_category, 
    delete_transaction, update_transaction, update_category_limit
)
from streamlit_cookies_manager import EncryptedCookieManager
import os

# Настройка страницы
st.set_page_config(page_title="Личные Финансы", page_icon="💸", layout="wide")

# Кастомные стили
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

# Инициализация менеджера куки
cookies = EncryptedCookieManager(
    prefix="bujet",
    password=os.environ.get("COOKIE_PASSWORD", "super_secret_default_password_for_cookies_123!")
)
if not cookies.ready():
    st.stop()

# Восстановление сессии из куки после обновления страницы (F5)
if 'user_id' not in st.session_state and cookies.get('user_id'):
    try:
        st.session_state['user_id'] = int(cookies.get('user_id'))
        st.session_state['username'] = cookies.get('username')
        st.session_state['group_id'] = int(cookies.get('group_id'))
    except Exception:
        pass

# Авторизация
if 'user_id' not in st.session_state:
    st.title("🔐 Вход в систему")
    
    tab_login, tab_register = st.tabs(["Вход", "Регистрация"])
    
    with tab_login:
        with st.form("login_form"):
            l_username = st.text_input("Логин")
            l_password = st.text_input("Пароль", type="password")
            submitted = st.form_submit_button("Войти")
            if submitted:
                user_id, group_id = verify_user(l_username, l_password)
                if user_id:
                    st.session_state['user_id'] = user_id
                    st.session_state['username'] = l_username
                    st.session_state['group_id'] = group_id
                    
                    cookies['user_id'] = str(user_id)
                    cookies['username'] = str(l_username)
                    cookies['group_id'] = str(group_id)
                    cookies.save()
                    st.rerun()
                else:
                    st.error("Неверный логин или пароль")
                    
    with tab_register:
        with st.form("register_form"):
            st.info("💡 Если вы хотите присоединиться к бюджету семьи, введите их код приглашения. Если вы оставите поле пустым, будет создана новая группа.")
            r_username = st.text_input("Придумайте логин")
            r_password = st.text_input("Придумайте пароль", type="password")
            r_password_confirm = st.text_input("Повторите пароль", type="password")
            r_invite_code = st.text_input("Код приглашения (необязательно)")
            
            registered = st.form_submit_button("Зарегистрироваться")
            if registered:
                if r_password != r_password_confirm:
                    st.error("Пароли не совпадают!")
                elif len(r_username) < 3 or len(r_password) < 5:
                    st.error("Логин от 3 символов, пароль от 5 символов.")
                else:
                    invite_code_val = r_invite_code.strip() if r_invite_code.strip() else None
                    user_id, group_id, err_msg = create_user(r_username, r_password, invite_code_val)
                    if err_msg:
                        st.error(err_msg)
                    else:
                        st.success("Регистрация успешна! Выполняется вход...")
                        st.session_state['user_id'] = user_id
                        st.session_state['username'] = r_username
                        st.session_state['group_id'] = group_id
                        
                        cookies['user_id'] = str(user_id)
                        cookies['username'] = str(r_username)
                        cookies['group_id'] = str(group_id)
                        cookies.save()
                        st.rerun()
    st.stop()

# --- ОСНОВНОЙ ИНТЕРФЕЙС ---
user_id = st.session_state['user_id']
group_id = st.session_state['group_id']

# --- Боковая панель ---
with st.sidebar:
    st.header(f"👤 {st.session_state['username']}")
    invite_code = get_invite_code(group_id)
    if invite_code:
        st.info(f"🔑 Код вашей семьи: **{invite_code}**\n\n(Поделитесь им для совместного ведения бюджета)")
    
    if st.button("🚪 Выйти"):
        st.info("Выход из системы...")
        # Очищаем сессию
        for key in ['user_id', 'username', 'group_id']:
            if key in st.session_state:
                del st.session_state[key]
        
        # Очищаем куки (заменяем на пустые строки)
        cookies['user_id'] = ""
        cookies['username'] = ""
        cookies['group_id'] = ""
        cookies.save()
        
        # Используем JS для жесткой перезагрузки страницы с небольшой задержкой (500мс),
        # чтобы React-компонент куки гарантированно успел сохранить изменения в браузере до обрыва сессии.
        import streamlit.components.v1 as components
        components.html("<script>setTimeout(function() { window.parent.location.reload(); }, 500);</script>", height=0)
        st.stop()
        
    st.divider()
    
    st.subheader("➕ Добавить операцию")
    with st.expander("Заполнить форму", expanded=True):
        t_type = st.radio("Тип операции", ["расход", "доход"], horizontal=True, key="t_type_radio")
        
        categories_df = get_categories(group_id, t_type)
        category_options = dict(zip(categories_df['name'], categories_df['id']))
        
        if category_options:
            selected_category_name = st.selectbox("Категория", list(category_options.keys()))
            amount = st.number_input("Сумма (₽)", min_value=0.01, step=100.0)
            date = st.date_input("Дата", datetime.date.today())
            description = st.text_input("Описание (необязательно)")
            
            if st.button("Добавить", type="primary", use_container_width=True):
                cat_id = category_options[selected_category_name]
                add_transaction(group_id, amount, cat_id, date, description, t_type)
                st.success("Успешно добавлено!")
                st.rerun()
        else:
            st.warning("Нет категорий для этого типа.")

    st.divider()

    st.subheader("📅 Период аналитики")
    today = datetime.date.today()
    first_day = today.replace(day=1)
    dates = st.date_input("Выберите диапазон дат", value=(first_day, today), key="date_range")
    
    if isinstance(dates, tuple) and len(dates) == 2:
        start_date, end_date = dates
    else:
        start_date, end_date = first_day, today

st.title("💸 Мой Бюджет")

# Проверка превышения лимитов
expenses_df_check = get_expenses_by_category(group_id, start_date, end_date)
over_limit_msgs = []
if not expenses_df_check.empty:
    for _, row in expenses_df_check.iterrows():
        limit = row.get('monthly_limit', 0)
        total = row['total']
        if limit > 0 and total > limit:
            over_limit_msgs.append(f"**{row['category']}** (превышение на {total - limit:,.0f} ₽)")

if over_limit_msgs:
    st.error("⚠️ **Внимание! Вы превысили установленный бюджет в категориях:**\n" + "\n".join([f"- {msg}" for msg in over_limit_msgs]))

# --- KPI Карточки ---
balance, income_period, expense_period = get_summary(group_id, start_date, end_date)

col1, col2, col3 = st.columns(3)
with col1:
    st.markdown(f"""
        <div class="metric-card balance">
            <div class="metric-label">Баланс семьи (всё время)</div>
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
    expenses_df = get_expenses_by_category(group_id, start_date, end_date)
    incomes_df = get_incomes_by_category(group_id, start_date, end_date)
    
    col_exp_chart, col_inc_chart = st.columns(2)
    
    with col_exp_chart:
        if not expenses_df.empty:
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
    expenses_df = get_expenses_by_category(group_id, start_date, end_date)
    
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
    cats_exp = get_categories(group_id, 'расход')
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
                update_category_limit(group_id, int(row['id']), float(row['monthly_limit']))
            st.success("Лимиты обновлены!")
            st.rerun()
    else:
        st.info("Нет категорий расходов.")

with tab_history:
    col_title, col_export = st.columns([3, 1])
    transactions_df = get_transactions(group_id, start_date, end_date)
    
    with col_export:
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
        
        editor_df = transactions_df.copy()
        
        edited_history = st.data_editor(
            editor_df[['id', 'date', 'type', 'category', 'amount', 'description']],
            column_config={
                "id": None, 
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
        
        if st.button("💾 Применить удаления", type="primary"):
            original_ids = set(transactions_df['id'])
            remaining_ids = set(edited_history['id'].dropna())
            deleted_ids = original_ids - remaining_ids
            
            if deleted_ids:
                for tx_id in deleted_ids:
                    delete_transaction(group_id, int(tx_id))
                st.success(f"Удалено операций: {len(deleted_ids)}")
                st.rerun()
            else:
                st.info("Изменений нет.")
    else:
        st.info("История пуста.")
