import time
import requests
import os

# Скрипт для предотвращения "засыпания" контейнера на Render (бесплатный тариф)
# Вы можете запустить его локально или как отдельный cron job.

RENDER_APP_URL = os.getenv("RENDER_APP_URL", "https://your-app-name.onrender.com")

def ping_app():
    while True:
        try:
            response = requests.get(RENDER_APP_URL)
            if response.status_code == 200:
                print(f"Ping successful at {time.strftime('%X')}")
            else:
                print(f"Ping failed with status code {response.status_code}")
        except Exception as e:
            print(f"Ping error: {e}")
        
        # Ping каждые 14 минут (Render засыпает после 15 минут неактивности)
        time.sleep(14 * 60)

if __name__ == "__main__":
    ping_app()
