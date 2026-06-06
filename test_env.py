from dotenv import load_dotenv
import os

load_dotenv()

print("YANDEX_BUCKET_NAME:", os.getenv("YANDEX_BUCKET_NAME"))
print("YANDEX_ACCESS_KEY_ID:", os.getenv("YANDEX_ACCESS_KEY_ID"))
print("YANDEX_SECRET_ACCESS_KEY:", os.getenv("YANDEX_SECRET_ACCESS_KEY")[:10] + "..." if os.getenv("YANDEX_SECRET_ACCESS_KEY") else None)
print("YANDEX_API_KEY:", os.getenv("YANDEX_API_KEY")[:10] + "..." if os.getenv("YANDEX_API_KEY") else None)

# Проверка на None
if not all([os.getenv("YANDEX_BUCKET_NAME"), 
            os.getenv("YANDEX_ACCESS_KEY_ID"), 
            os.getenv("YANDEX_SECRET_ACCESS_KEY"),
            os.getenv("YANDEX_API_KEY")]):
    print("\n❌ НЕ ВСЕ переменные загружены!")
else:
    print("\n✅ Все переменные найдены")