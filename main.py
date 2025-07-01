from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import pandas as pd
import pytesseract
from PIL import Image
import io
import re
import csv
import cv2
import numpy as np
import os
import joblib
from datetime import datetime
import random
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from fastapi import HTTPException
from bson.objectid import ObjectId
from fastapi import Query
from dotenv import load_dotenv


load_dotenv()  # Load from .env file


vectorizer = joblib.load("vectorizer.pkl")
model = joblib.load("classifier.pkl")

from routes import analytics
from routes import auth

import certifi
from pymongo import MongoClient


import os


MONGO_URI = os.getenv("MONGO_URI")

client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db = client["expense_tracker"]
collection = db["expenses"]


def serialize_expense(exp):
    return {
        "id": str(exp["_id"]),
        "date": exp["date"],
        "description": exp["description"],
        "amount": float(exp["amount"]),
        "category": exp["category"]
    }

app = FastAPI()
app.include_router(analytics.router)
app.include_router(auth.router)


UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development only
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Helper to save to unified CSV
def append_to_expense_log(date, desc, amount, category, email=None):
    # CSV Logging (optional)
    file_path = os.path.join(UPLOAD_DIR, "expense_log.csv")
    with open(file_path, mode='a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([date, desc, amount, category, email])

    # MongoDB Logging
    mongo_doc = {
        "date": pd.to_datetime(date, errors='coerce'),
        "description": desc,
        "amount": float(amount),
        "category": category,
        "email": email  # ✅ NEW
    }
    collection.insert_one(mongo_doc)

@app.get("/")
def root():
    return {"message": "SmartSpend backend is working!"}

@app.get("/sync-csv-to-mongo")
def sync_csv():
    df = pd.read_csv("uploads/expense_log.csv", header=None, names=["Date", "Description", "Amount", "Category"])
    df["Date"] = pd.to_datetime(df["Date"], errors='coerce')
    df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
    df = df.dropna(subset=["Date", "Amount"])

    records = df.to_dict(orient="records")

    for r in records:
        r["date"] = r.pop("Date")
        r["description"] = r.pop("Description")
        r["amount"] = float(r.pop("Amount"))
        r["category"] = r.pop("Category")

    collection.insert_many(records)

    return {"message": f"{len(records)} records synced to MongoDB."}

@app.get("/ping")
def ping():
    return {"message": "Server is up!"}

# 1. Upload CSV
from fastapi import UploadFile, File
import pandas as pd
import io

from fastapi import Form  # Add to imports if not already present

@app.post("/upload/csv/")
async def upload_csv(file: UploadFile = File(...), email: str = Form(...)):
    try:
        contents = await file.read()

        filename = file.filename.lower()
        if filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(contents))
        elif filename.endswith(".xlsx") or filename.endswith(".xls"):
            df = pd.read_excel(io.BytesIO(contents))
        else:
            return {"error": "Unsupported file format. Please upload a .csv or .xlsx file."}

        required_columns = {"Date", "Description", "Amount"}
        if not required_columns.issubset(df.columns):
            return {"error": f"File must contain columns: {required_columns}"}

        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
        df = df.dropna(subset=["Date", "Description", "Amount"])
        df["Category"] = df["Description"].apply(categorize_text)

        for _, row in df.iterrows():
            formatted_date = row["Date"].strftime("%Y-%m-%d")
            append_to_expense_log(
                date=formatted_date,
                desc=row["Description"],
                amount=row["Amount"],
                category=row["Category"],
                email=email  # ✅ Pass email
            )

        return {"message": f"{len(df)} entries uploaded and categorized successfully."}

    except Exception as e:
        return {"error": str(e)}



# ⬅️ Image Preprocessing Function
def preprocess_image(image: Image.Image) -> Image.Image:
    img = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    processed = cv2.bitwise_not(thresh)
    return Image.fromarray(processed)

# 2. Upload Receipt Image
@app.post("/upload/receipt/")
async def upload_receipt(file: UploadFile = File(...), email: str = Form(...)):
    print("➡️ Upload received")
    image_data = await file.read()

    try:
        image = Image.open(io.BytesIO(image_data))
        print("🖼️ Original Image loaded")

        # Apply preprocessing
        image = preprocess_image(image)
        print("🧪 Image preprocessed")

        # OCR
        custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.:/$ '
        text = pytesseract.image_to_string(image, config=custom_config)

        print("🔍 Raw OCR Text:\n", text)

        items, date = extract_items_from_text(text)
        print("📦 Items parsed:", items)
        print("🗓️ Date detected:", date)

        receipt_date = date if date else "Unknown"

        for item in items:
            append_to_expense_log(
                date=receipt_date,
                desc=item['name'],
                amount=item['price'],
                category=item['category'],
                email=email  # ✅ Pass email
            )

        return {
            "message": "Receipt processed successfully.",
            "date": receipt_date,
            "items": items
        }

    except Exception as e:
        print("❌ ERROR:", str(e))
        return {"error": str(e)}


# Item + Price extraction logic
def extract_items_from_text(text):
    lines = text.split("\n")
    results = []
    receipt_date = None

        # Try to extract date like MM/DD/YYYY or DD/MM/YYYY or DD-MM-YYYY
    date_patterns = [
        r'(\d{2}/\d{2}/\d{4})',
        r'(\d{2}-\d{2}-\d{4})',
        r'(\d{4}-\d{2}-\d{2})',
    ]
    for line in lines:
        for pattern in date_patterns:
            match = re.search(pattern, line)
            if match:
                receipt_date = match.group(1)
                break
        if receipt_date:
            break



    skip_keywords = [
        "suite", "palo alto", "terminal", "order id", "order number",
        "merchant", "approval code", "transaction id", "grand total", 
        "subtotal", "tip", "signature", "card type", "visa", "response",
        "amount", "entry mode", "number", "local business", "total", "total usd"
    ]

    for line in lines:
        line = line.strip()
        if not line or len(line) < 4:
            continue

        if any(k in line.lower() for k in skip_keywords):
            continue

        match = re.match(r"(.+?)[\s\.]*[\$₹]?\s*(\d{1,5}(?:\.\d{2})?)\s*$", line)
        if match:
            name = match.group(1).strip()
            price = float(match.group(2))

            # 🛑 NEW FILTER: Remove IDs, phone-like
            if re.search(r"\d{2,}-?\d{2,}", line):
                print("🚫 Skipped (Phone-like):", line)
                continue

            if name.replace(" ", "").isdigit() or len(name) < 2:
                print("🚫 Skipped (Name is just digits):", name)
                continue

            if price > 100000 and name.lower() not in ['rent', 'flight', 'insurance']:
                print("🚫 Skipped (Price too high for food):", price)
                continue

            results.append({
                "name": name,
                "price": price,
                "category": categorize_text(name)
            })
        else:
            print("🚫 Skipped (No Match or Blocked):", line)

    return results, receipt_date

import re

def categorize_text(text):
    text = text.lower().strip()
    text = re.sub(r'[^a-z\s]', '', text)  # remove punctuation/numbers
    if not text or len(text.split()) > 4:  # avoid long irrelevant phrases
        return "Other"
    X = vectorizer.transform([text])
    return model.predict(X)[0]

# --- Helper: Convert ObjectId to string for JSON ---
def serialize_expense(expense):
    expense["id"] = str(expense["_id"])   # ✅ Add this
    del expense["_id"]                    # ✅ Optional, removes the Mongo `_id`
    return expense


# 🚀 ADD EXPENSE
@app.post("/expenses")
def add_expense(expense: dict):
    if "email" not in expense:
        raise HTTPException(status_code=400, detail="Missing user email")

    result = collection.insert_one(expense)
    expense["_id"] = str(result.inserted_id)
    return {"message": "Added", "id": str(result.inserted_id), "expense": expense}


# ✏️ UPDATE EXPENSE
@app.put("/expenses/{id}")
def update_expense(id: str, expense: dict):
    if "_id" in expense:
        del expense["_id"]

    if "email" not in expense:
        raise HTTPException(status_code=400, detail="Missing user email")

    result = collection.update_one({"_id": ObjectId(id), "email": expense["email"]}, {"$set": expense})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Expense not found or not owned by user")
    return {"message": "Updated"}


# ❌ DELETE EXPENSE
@app.delete("/expenses/{id}")
def delete_expense(id: str, email: str = Query(...)):
    result = collection.delete_one({"_id": ObjectId(id), "email": email})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Expense not found or not owned by user")
    return {"message": "Deleted"}


# 📥 GET ALL EXPENSES (for viewing/updating UI)


@app.get("/expenses")
def get_all_expenses(email: str = Query(...)):
    all_expenses = list(collection.find({"email": email}))
    return [serialize_expense(exp) for exp in all_expenses]
