from pymongo import MongoClient
from datetime import datetime
import random

# --- MongoDB Setup ---
client = MongoClient("mongodb://localhost:27017")
db = client["expense_tracker"]
collection = db["expenses"]

# --- Descriptions with realistic price ranges ---
descriptions = {
    "Food": [("Pizza", 200, 350), ("Burger", 100, 250), ("Noodles", 150, 300)],
    "Groceries": [("Rice", 100, 200), ("Milk", 30, 60), ("Eggs", 50, 100)],
    "Transport": [("Uber", 150, 500), ("Train", 50, 200), ("Bus", 20, 100)],
    "Rent": [("Flat Rent", 8000, 20000)],
    "Entertainment": [("Cinema", 200, 500), ("Shopping", 500, 3000), ("Manicure", 250, 500), ("Pedicure", 250, 500)],
    "Self-care": [("Moisturiser", 150, 500), ("Lipbalm", 50, 200)],
    "Utility": [("Broom", 100, 200), ("Curtains", 500, 1500)],
    "Electronics": [("Earphones", 800, 2500), ("Battery", 100, 500)]
}

# --- Dummy Data Generation ---
dummy_data = []
for month in [1, 2, 3]:  # Jan to March
    for _ in range(15):  # 15 entries/month
        category = random.choice(list(descriptions.keys()))
        item, min_price, max_price = random.choice(descriptions[category])
        amount = round(random.uniform(min_price, max_price), 2)
        date = datetime(2025, month, random.randint(1, 28))

        dummy_data.append({
            "date": date,
            "description": item,
            "amount": amount,
            "category": category
        })

# --- Insert into MongoDB ---
collection.insert_many(dummy_data)
print(f"✅ Inserted {len(dummy_data)} dummy expense records into MongoDB!")
