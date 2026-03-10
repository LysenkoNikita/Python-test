import pytest
import base64
import shutil
from pathlib import Path
from io import BytesIO
from fastapi.testclient import TestClient
from api import app
import uuid
from PIL import Image

client = TestClient(app)

VALID_KEY = "1623bce0-4011-4904-8222-1b1af9068399"
INVALID_KEY = "invalid_key_12345"
EMPTY_KEY = ""
WHITESPACE_KEY = "   "
SPECIAL_CHARS_KEY = "!@#$%^&*()_+-=[]{}|;':\",./<>?"

created_pet_ids = []


def create_test_image():
    """Создает тестовое изображение"""
    img = Image.new('RGB', (100, 100), color='red')
    img_bytes = BytesIO()
    img.save(img_bytes, format='JPEG')
    img_bytes.seek(0)
    return img_bytes


class TestAuthentication:
    """Тесты аутентификации - 5 тестов"""

    def test_auth_valid_credentials(self):
        """Тест 1: Успешная аутентификация с валидными данными"""
        response = client.get("/api/key", params={
            "username": "str",
            "password": "str"
        })
        assert response.status_code == 200
        data = response.json()
        assert "api_key" in data
        assert data["api_key"] == VALID_KEY

    def test_auth_invalid_username(self):
        """Тест 2: Аутентификация с неверным username"""
        response = client.get("/api/key", params={
            "username": "wrong_user",
            "password": "str"
        })
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
        assert "Invalid username or password" in data["detail"]

    def test_auth_invalid_password(self):
        """Тест 3: Аутентификация с неверным паролем"""
        response = client.get("/api/key", params={
            "username": "str",
            "password": "wrong_pass"
        })
        assert response.status_code == 401

    def test_auth_empty_username(self):
        """Тест 4: Аутентификация с пустым username"""
        response = client.get("/api/key", params={
            "username": "",
            "password": "str"
        })
        assert response.status_code == 401

    def test_auth_empty_password(self):
        """Тест 5: Аутентификация с пустым паролем"""
        response = client.get("/api/key", params={
            "username": "str",
            "password": ""
        })
        assert response.status_code == 401


class TestPetsList:
    """Тесты получения списка питомцев - 3 теста"""

    def test_list_pets_valid_key(self):
        """Тест 6: Получение списка питомцев с валидным ключом"""
        response = client.get(
            "/api/pets",
            headers={"auth_key": VALID_KEY}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_list_pets_invalid_key(self):
        """Тест 7: Получение списка питомцев с неверным ключом"""
        response = client.get(
            "/api/pets",
            headers={"auth_key": INVALID_KEY}
        )
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
        assert "Invalid or missing API key" in data["detail"]

    def test_list_pets_missing_key(self):
        """Тест 8: Получение списка питомцев без ключа"""
        response = client.get("/api/pets")
        assert response.status_code == 401


class TestCreatePetSimple:
    """Тесты создания питомца (простой метод) - 7 тестов"""

    def test_create_pet_simple_valid(self):
        """Тест 9: Создание питомца с валидными данными"""
        response = client.post(
            "/api/create_pet_simple",
            headers={"auth_key": VALID_KEY},
            params={
                "animal_type": "dog",
                "name": "Rex",
                "age": 3
            }
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Rex"
        assert data["animal_type"] == "dog"
        assert data["age"] == 3
        assert "id" in data
        assert data["pet_photo"] is None
        created_pet_ids.append(data["id"])

    def test_create_pet_simple_min_age(self):
        """Тест 10: Создание питомца с минимальным возрастом (0 лет)"""
        response = client.post(
            "/api/create_pet_simple",
            headers={"auth_key": VALID_KEY},
            params={
                "animal_type": "cat",
                "name": "Kitty",
                "age": 0
            }
        )
        assert response.status_code == 201
        data = response.json()
        assert data["age"] == 0
        created_pet_ids.append(data["id"])

    def test_create_pet_simple_max_age(self):
        """Тест 11: Создание питомца с максимальным возрастом (50 лет)"""
        response = client.post(
            "/api/create_pet_simple",
            headers={"auth_key": VALID_KEY},
            params={
                "animal_type": "turtle",
                "name": "Old Turtle",
                "age": 50
            }
        )
        assert response.status_code == 201
        data = response.json()
        assert data["age"] == 50
        created_pet_ids.append(data["id"])

    def test_create_pet_simple_min_name_length(self):
        """Тест 12: Создание питомца с минимальной длиной имени (2 символа)"""
        response = client.post(
            "/api/create_pet_simple",
            headers={"auth_key": VALID_KEY},
            params={
                "animal_type": "bird",
                "name": "Ki",
                "age": 1
            }
        )
        assert response.status_code == 201
        data = response.json()
        assert len(data["name"]) == 2
        created_pet_ids.append(data["id"])

    def test_create_pet_simple_max_name_length(self):
        """Тест 13: Создание питомца с максимальной длиной имени (40 символов)"""
        name = "A" * 40
        response = client.post(
            "/api/create_pet_simple",
            headers={"auth_key": VALID_KEY},
            params={
                "animal_type": "fish",
                "name": name,
                "age": 2
            }
        )
        assert response.status_code == 201
        data = response.json()
        assert len(data["name"]) == 40
        created_pet_ids.append(data["id"])

    def test_create_pet_simple_invalid_age_negative(self):
        """Тест 14: Создание питомца с отрицательным возрастом"""
        response = client.post(
            "/api/create_pet_simple",
            headers={"auth_key": VALID_KEY},
            params={
                "animal_type": "dog",
                "name": "Bad Age",
                "age": -1
            }
        )
        assert response.status_code == 400
        data = response.json()
        assert "Age cannot be negative" in data["detail"]

    def test_create_pet_simple_age_too_high(self):
        """Тест 15: Создание питомца с возрастом больше 50"""
        response = client.post(
            "/api/create_pet_simple",
            headers={"auth_key": VALID_KEY},
            params={
                "animal_type": "dog",
                "name": "Too Old",
                "age": 51
            }
        )
        assert response.status_code == 400
        data = response.json()
        assert "maximum allowed is 50 years" in data["detail"]


class TestCreatePetWithPhoto:
    """Тесты создания питомца с фото - 5 тестов"""

    def test_create_pet_with_photo_valid(self):
        """Тест 16: Создание питомца с валидным фото"""
        img_bytes = create_test_image()
        files = {
            'pet_photo': ('test.jpg', img_bytes, 'image/jpeg')
        }
        data = {
            'animal_type': 'cat',
            'name': 'Photo Cat',
            'age': 2
        }

        response = client.post(
            "/api/pets",
            headers={"auth_key": VALID_KEY},
            data=data,
            files=files
        )
        assert response.status_code == 201
        result = response.json()
        assert result['name'] == 'Photo Cat'
        assert result['pet_photo'] is not None
        assert 'files' in result['pet_photo']
        assert result['pet_photo'].endswith('.jpg') or result['pet_photo'].endswith('.jpeg')

    def test_create_pet_with_photo_unsupported_format(self):
        """Тест 17: Загрузка фото неподдерживаемого формата"""
        files = {
            'pet_photo': ('test.txt', BytesIO(b'fake text content'), 'text/plain')
        }
        data = {
            'animal_type': 'cat',
            'name': 'Bad Photo',
            'age': 2
        }

        response = client.post(
            "/api/pets",
            headers={"auth_key": VALID_KEY},
            data=data,
            files=files
        )
        assert response.status_code == 400
        data = response.json()
        assert "File format not supported" in data["detail"]

    def test_create_pet_with_photo_too_large(self):
        """Тест 18: Загрузка фото превышающего лимит (8MB)"""
        # Создаем большой файл (9MB)
        large_data = b'0' * (9 * 1024 * 1024)
        files = {
            'pet_photo': ('large.jpg', BytesIO(large_data), 'image/jpeg')
        }
        data = {
            'animal_type': 'cat',
            'name': 'Large Photo',
            'age': 2
        }

        response = client.post(
            "/api/pets",
            headers={"auth_key": VALID_KEY},
            data=data,
            files=files
        )
        assert response.status_code == 400
        data = response.json()
        assert "File size exceeds 8MB limit" in data["detail"]

    def test_create_pet_without_photo(self):
        """Тест 19: Создание питомца без фото (только данные)"""
        data = {
            'animal_type': 'dog',
            'name': 'No Photo',
            'age': 3
        }

        response = client.post(
            "/api/pets",
            headers={"auth_key": VALID_KEY},
            data=data
        )
        assert response.status_code == 201
        result = response.json()
        assert result['name'] == 'No Photo'
        assert result['pet_photo'] is None
        created_pet_ids.append(result['id'])

    def test_create_pet_with_photo_empty_file(self):
        """Тест 20: Создание питомца с пустым файлом фото"""
        files = {
            'pet_photo': ('empty.jpg', BytesIO(b''), 'image/jpeg')
        }
        data = {
            'animal_type': 'bird',
            'name': 'Empty Photo',
            'age': 1
        }

        response = client.post(
            "/api/pets",
            headers={"auth_key": VALID_KEY},
            data=data,
            files=files
        )
        # Пустой файл должен обрабатываться как отсутствие фото или ошибка
        # В зависимости от реализации API
        assert response.status_code in [201, 400]


if __name__ == "__main__":
    pytest.main([
        "test_api_extended.py",
        "-v",
        "--tb=short",
        "-x",
        "--maxfail=1"
    ])