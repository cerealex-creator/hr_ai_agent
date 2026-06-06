import boto3
import os
from dotenv import load_dotenv

load_dotenv()

print("🔍 Тест подключения к Yandex Object Storage...")
print()

# Получаем переменные
bucket = os.getenv("YANDEX_BUCKET_NAME")
access_key = os.getenv("YANDEX_ACCESS_KEY_ID")
secret_key = os.getenv("YANDEX_SECRET_ACCESS_KEY")

print(f"📦 Бакет: {bucket}")
print(f"🔑 Access Key: {access_key[:10]}...")
print(f"🔒 Secret Key: {secret_key[:10]}...")
print()

try:
    # Создаем клиент
    session = boto3.session.Session()
    s3 = session.client(
        service_name='s3',
        endpoint_url='https://storage.yandexcloud.net',
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key
    )
    
    # Проверяем существование бакета
    print("🔄 Проверяем бакет...")
    s3.head_bucket(Bucket=bucket)
    print("✅ Бакет существует и доступен!")
    print()
    
    # Пробуем загрузить тестовый файл
    test_file = "test_audio.wav"
    
    # Создаем dummy файл
    print("🔄 Создаю тестовый файл...")
    with open(test_file, "wb") as f:
        f.write(b"dummy audio content")  # Просто какой-то контент
    
    print(f"🔄 Загружаю файл {test_file} в бакет {bucket}...")
    s3.upload_file(test_file, bucket, test_file)
    print("✅ Файл загружен!")
    
    # Формируем публичную ссылку
    url = f"https://storage.yandexcloud.net/{bucket}/{test_file}"
    print(f"🔗 Публичная ссылка: {url}")
    print()
    print("🎉 Всё работает!")
    
    # Удаляем тестовый файл
    os.remove(test_file)
    
except Exception as e:
    print("❌ ОШИБКА:")
    print(f"{type(e).__name__}: {e}")
    print()
    print("💡 Возможные причины:")
    print("1. Бакет не существует")
    print("2. Бакет не публичный")
    print("3. Неверные ключи доступа")
    print("4. Недостаточно прав у сервисного аккаунта")