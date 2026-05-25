#!/bin/bash
# Запускаем скрипт-пинговальщик в фоновом режиме
python ping_script.py &

# Запускаем Streamlit на порту, который выдает Render (переменная $PORT)
exec streamlit run app.py --server.port=${PORT:-8501} --server.address=0.0.0.0
