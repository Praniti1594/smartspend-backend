from fastapi import APIRouter, HTTPException
from models.user import UserCreate, UserLogin
from pymongo import MongoClient
from bson.objectid import ObjectId
import bcrypt
import certifi

router = APIRouter()

# Atlas Connection
MONGO_URI = "mongodb+srv://pranitikubal9:WRHrz8m32NqaFMiN@cluster0.c6as14a.mongodb.net/?retryWrites=true&w=majority"
client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())

# Use the same database as expenses, but a separate collection
db = client["expense_tracker"]
users = db["users"]

@router.post("/register")
async def register(user: UserCreate):
    if users.find_one({"email": user.email}):
        raise HTTPException(status_code=400, detail="Email already exists")

    hashed_pw = bcrypt.hashpw(user.password.encode('utf-8'), bcrypt.gensalt())
    users.insert_one({
        "name": user.name,
        "email": user.email,
        "password": hashed_pw
    })
    return {"message": "User registered successfully!"}

@router.post("/login")
async def login(user: UserLogin):
    db_user = users.find_one({"email": user.email})
    if not db_user:
        raise HTTPException(status_code=400, detail="User not found")

    if not bcrypt.checkpw(user.password.encode('utf-8'), db_user["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return {
        "message": "Login successful",
        "user": {
            "id": str(db_user["_id"]),
            "name": db_user["name"],
            "email": db_user["email"]
        }
    }
