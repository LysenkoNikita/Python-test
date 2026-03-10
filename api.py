from fastapi import FastAPI, HTTPException, UploadFile, File, Header, status, Form, Depends
import uuid
import base64
from pathlib import Path
from datetime import datetime
from typing import Optional
from uuid import uuid4
import uvicorn

app = FastAPI(title="Pet API", description="API for managing pets", version="1.0.0")

user_database = {
    '1623bce0-4011-4904-8222-1b1af9068399': {
        "username": "str",
        "password": "str"
    }
}

pet_collection = []
VALID_SPECIES = ["dog", "cat", "bird", "fish", "rabbit", "hamster", "turtle", "parrot", "lizard", "other"]

FILES_DIR = Path("files")
FILES_DIR.mkdir(parents=True, exist_ok=True)


def validate_api_key(api_key: str) -> bool:
    """Проверяем нахождение ключа в нашей 'базе'"""
    return api_key in user_database


def get_current_user(authorization: Optional[str] = Header(None, alias="auth_key")) -> str:
    """
    Получаем пользователя по его ключу
    """
    if not authorization or not validate_api_key(authorization):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "API-Key"}
        )
    return authorization


@app.get("/api/key", status_code=status.HTTP_200_OK)
def generate_api_key(username: str, password: str):
    """
    Авторизируем пользователя по логину и паролю.
    Возвращаем ключ
    """
    for api_key, credentials in user_database.items():
        if credentials["username"] == username and credentials["password"] == password:
            return {
                "api_key": api_key
            }

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid username or password "
    )


@app.get("/api/pets", status_code=status.HTTP_200_OK)
def list_pets(
        current_user: str = Depends(get_current_user),
        scope: Optional[str] = "my_pets"
):
    """
    Проверяем питомцев на владельцев и возвращаем нужных
    """
    if scope == "my_pets":
        user_pets = [pet for pet in pet_collection if pet["user_id"] == current_user]
        return user_pets

    return pet_collection


@app.post("/api/create_pet_simple", status_code=status.HTTP_201_CREATED)
def create_pet_basic(
        animal_type: str,
        name: str,
        age: int,
        current_user: str = Depends(get_current_user)
):
    """
    Простое создание питомца
    """
    if not animal_type or not animal_type.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Species field cannot be empty"
        )

    if not name or not name.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Pet name is required"
        )

    if age < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Age cannot be negative"
        )

    if age > 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Age seems too high - maximum allowed is 50 years"
        )


    cleaned_animal_type = animal_type.strip().lower()

    if cleaned_animal_type not in VALID_SPECIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Species must be one of: {', '.join(VALID_SPECIES)}"
        )

    cleaned_name = name.strip()
    if len(cleaned_name) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Pet name must contain at least 2 characters"
        )

    if len(cleaned_name) > 40:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Pet name is too long (maximum 40 characters)"
        )

    pet_id = str(uuid.uuid4())
    current_timestamp = datetime.now().isoformat()

    new_pet = {
        "id": pet_id,
        "user_id": current_user,
        "animal_type": cleaned_animal_type,
        "name": cleaned_name,
        "age": age,
        "pet_photo": None,
        "created_at": current_timestamp,
        "last_updated": current_timestamp
    }

    pet_collection.append(new_pet)

    return new_pet


@app.post("/api/pets", status_code=status.HTTP_201_CREATED)
async def create_pet_with_image(
        animal_type: str = Form(...),
        name: str = Form(...),
        age: int = Form(...),
        pet_photo: UploadFile = File(None),
        current_user: str = Depends(get_current_user)
):
    """
    Создание питомца
    """
    if not animal_type or not animal_type.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="animal_type is required"
        )

    if not name  or not name .strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Pet name is required"
        )

    if age < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Age cannot be negative"
        )

    if age > 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Age exceeds maximum allowed (50 years)"
        )

    species_normalized = animal_type.strip().lower()

    if species_normalized not in VALID_SPECIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid species. Choose from: {', '.join(VALID_SPECIES)}"
        )

    name_normalized = name.strip()
    if len(name_normalized) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Pet name must be at least 2 characters long"
        )

    if len(name_normalized) > 40:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Pet name cannot exceed 40 characters"
        )

    for existing_pet in pet_collection:
        if existing_pet["user_id"] == current_user and existing_pet["name"].lower() == name_normalized.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You already have a pet with this name. Please choose a different name."
            )

    photo_url = None
    if pet_photo and pet_photo.filename:
        try:
            content_length = pet_photo.size
            if content_length and content_length > 8 * 1024 * 1024:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="File size exceeds 8MB limit. Please compress your image."
                )
        except AttributeError:
            try:
                MAX_SIZE = 8 * 1024 * 1024
                image_data = await pet_photo.read(MAX_SIZE + 1)

                if len(image_data) > MAX_SIZE:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="File size exceeds 8MB limit. Please compress your image."
                    )
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Error reading file: {str(e)}"
                )

        ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
        ALLOWED_MIME_TYPES = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp']

        file_extension = Path(pet_photo.filename).suffix.lower()

        if file_extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File format not supported. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
            )

        if pet_photo.content_type not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file type. Only image files are accepted."
            )

        try:
            if 'image_data' not in locals():
                image_data = await pet_photo.read()

            filename = f"{uuid4().hex}{file_extension}"
            filepath = FILES_DIR / filename

            with open(filepath, "wb") as buffer:
                buffer.write(image_data)

            photo_url = str(filepath)

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error saving image: {str(e)}"
            )

    pet_id = str(uuid.uuid4())
    current_timestamp = datetime.now().isoformat()

    new_pet = {
        "id": pet_id,
        "user_id": current_user,
        "animal_type": species_normalized,
        "name": name_normalized,
        "age": age,
        "pet_photo": photo_url,
        "created_at": current_timestamp,
        "last_updated": current_timestamp
    }

    pet_collection.append(new_pet)

    return {
        "id": pet_id,
        "user_id": current_user,
        "animal_type": species_normalized,
        "name": name_normalized,
        "age": age,
        "pet_photo": photo_url,
        "created_at": current_timestamp,
    }


@app.delete("/api/pets/{pet_id}", status_code=status.HTTP_200_OK)
def remove_pet(
        pet_id: str,
        current_user: str = Depends(get_current_user)
):
    """
    Удаление питомца по id
    """
    for index, pet in enumerate(pet_collection):
        if pet["id"] == pet_id:
            if pet["user_id"] != current_user:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You are not authorized to delete this pet"
                )

            removed_pet = pet_collection.pop(index)

            if removed_pet.get("pet_photo"):
                try:
                    photo_path = Path(removed_pet["pet_photo"])
                    if photo_path.exists():
                        photo_path.unlink()
                except Exception:
                    print(f"Warning: Could not delete photo file for pet {pet_id}")

            return

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Pet with ID {pet_id} not found"
    )


@app.put("/api/pets/{pet_id}", status_code=status.HTTP_200_OK)
def modify_pet(
        pet_id: str,
        name: Optional[str] = None,
        animal_type: Optional[str] = None,
        age: Optional[int] = None,
        current_user: str = Depends(get_current_user)
):
    """
    Обновление информации о питомце
    """
    for pet in pet_collection:
        if pet["id"] == pet_id:
            if pet["user_id"] != current_user:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have permission to modify this pet"
                )

            if name is not None:
                pet["name"] = name.strip()
            if age is not None:
                pet["age"] = age
            if animal_type is not None:
                pet["animal_type"] = animal_type.strip().lower()

            pet["last_updated"] = datetime.now().isoformat()

            return pet

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Pet with ID {pet_id} does not exist"
    )


@app.post("/api/pets/set_photo/{pet_id}", status_code=status.HTTP_200_OK)
async def update_pet_photo(
        pet_id: str,
        pet_photo: UploadFile = File(...),
        current_user: str = Depends(get_current_user)
):
    """
    Загрузка или обновление фото питомца
    """
    target_pet = None
    for pet in pet_collection:
        if pet["id"] == pet_id:
            target_pet = pet
            break

    if not target_pet:
        raise HTTPException(
            status_code=404,
            detail=f"No pet found with ID {pet_id}"
        )

    if target_pet["user_id"] != current_user:
        raise HTTPException(
            status_code=403,
            detail="You can only modify photos of your own pets"
        )

    SUPPORTED_FORMATS = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp']
    SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}

    file_extension = Path(pet_photo .filename).suffix.lower()

    if pet_photo .content_type not in SUPPORTED_FORMATS or file_extension not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Only JPG, JPEG, PNG, and WEBP images are supported"
        )

    MAX_PHOTO_SIZE = 8 * 1024 * 1024

    try:
        image_data = await pet_photo.read()
        file_size = len(image_data)

        if file_size > 8 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File size exceeds 8MB limit. Please compress your image."
            )

        filename = f"{uuid4().hex}{file_extension}"
        filepath = FILES_DIR / filename

        with open(filepath, "wb") as buffer:
            buffer.write(image_data)

        photo_url = str(filepath)

        target_pet["pet_photo"] = photo_url

        target_pet["last_updated"] = datetime.now().isoformat()

        if "created_at" not in target_pet:
            target_pet["created_at"] = datetime.now().isoformat()

        return {
            "id": target_pet.get("id", pet_id),
            "name": target_pet.get("name", ""),
            "animal_type": target_pet.get("animal_type", ""),
            "age": target_pet.get("age", 0),
            "pet_photo": photo_url,
            "user_id": target_pet.get("user_id", current_user),
            "created_at": target_pet.get("created_at", datetime.now().isoformat())
        }

    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process image: {str(error)}"
        )


if __name__ == "__main__":
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )