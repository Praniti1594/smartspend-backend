import spacy
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB

# Load spaCy
nlp = spacy.load("en_core_web_sm")

# Preprocess using spaCy
def preprocess(text):
    doc = nlp(text.lower().strip())
    tokens = [token.lemma_ for token in doc if not token.is_stop and token.is_alpha]
    return " ".join(tokens)

# ✅ Expanded labeled examples
# ✅ Updated labeled examples
texts = [
    # Food
    "coffee", "latte", "burger", "apple pie", "brownies","qappuccino", "pizza", "sandwich", "fries", "tea", "muffin",
    "restaurant", "dinner", "breakfast", "snack", "ice cream", "biryani", "cafe", "noodles", "thali", "roll",

    # Groceries
    "grocery", "supermarket", "milk", "bread", "rice", "vegetables", "eggs", "flour", "grains", "oil",
    "ghee", "butter", "dal", "atta", "paneer", "salt", "sugar",

    # Utilities (NEW)
    "soap bar", "detergent", "toilet cleaner", "broom", "floor cleaner", "dishwashing liquid", "mop", "tissue paper", "garbage bag", "bleach",

    # Transport
    "uber", "ola", "taxi", "bus ticket", "train fare", "auto", "cab", "train", "metro", "flight fare",
    "gas", "petrol", "diesel", "parking", "toll", "plane ticket",

    # Clothing
    "shirt", "jeans", "jacket", "clothing", "dress", "tshirt", "skirt", "saree", "trousers", "kurti",
    "handbag", "wallet", "purse", "shoes", "heels", "slippers", "blouse", "cap", "scarf", "gloves",

    # Entertainment
    "movie ticket", "netflix", "cinema", "popcorn", "concert", "spotify", "music subscription", "theme park",
    "game", "app subscription", "youtube premium", "book", "amazon prime",

    # Electronics
    "laptop", "phone", "charger", "usb cable", "earphones", "power bank", "headphones", "keyboard", "monitor",
    "mouse", "hard disk", "bluetooth speaker", "smartwatch", "tablet",

    # Personal care
    "perfume", "soap", "shampoo", "facewash", "lotion", "cream", "toothpaste", "deodorant",
    "makeup", "sunscreen", "nail polish", "conditioner", "moisturizer", "lipstick", "sanitary napkins",

    # Other / Misc
    "insurance", "rent", "total", "tip", "signature", "donation", "repair", "bill payment",
    "fine", "penalty", "tax", "fee", "emi", "loan", "maintenance", "subscription"
]

labels = [
    # Food
    *["Food"] * 21,

    # Groceries
    *["Groceries"] * 17,

    # Utilities
    *["Utilities"] * 10,

    # Transport
    *["Transport"] * 15,

    # Clothing
    *["Clothing"] * 20,

    # Entertainment
    *["Entertainment"] * 15,

    # Electronics
    *["Electronics"] * 15,

    # Personal care
    *["Personal Care"] * 15,

    # Other / Misc
    *["Other"] * 14
]


# Apply preprocessing
processed_texts = [preprocess(t) for t in texts]

# Vectorize
vectorizer = TfidfVectorizer()
X = vectorizer.fit_transform(processed_texts)

# Train model
model = MultinomialNB()
model.fit(X, labels)

# Save the vectorizer and model
joblib.dump(vectorizer, "vectorizer.pkl")
joblib.dump(model, "classifier.pkl")

print("✅ Updated model and vectorizer saved.")
