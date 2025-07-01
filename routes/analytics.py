from fastapi import APIRouter
import pandas as pd
import os
from pymongo import MongoClient
import certifi

MONGO_URI = os.getenv("MONGO_URI")

client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db = client["expense_tracker"]
collection = db["expenses"]

def get_expenses_df(email: str):
    data = list(collection.find({"email": email}))

    if not data:
        return pd.DataFrame()
    
    df = pd.DataFrame(data)
    
    # Normalize/clean
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    df["category"] = df.get("category", "Other")
    df = df.rename(columns={
        "date": "Date",
        "description": "Description",
        "amount": "Amount",
        "category": "Category"
    })

    return df.dropna(subset=["Date", "Amount"])

router = APIRouter()

@router.get("/analytics/category-breakdown")
def category_breakdown(email: str):
    df = get_expenses_df(email)
    
    # Ensure Amount is numeric
    df["Amount"] = pd.to_numeric(df["Amount"], errors='coerce')
    df = df.dropna(subset=["Amount"])

    grouped = df.groupby("Category")["Amount"].sum().reset_index()

    return [{"name": row["Category"], "value": round(row["Amount"], 2)} for _, row in grouped.iterrows()]

@router.get("/analytics/weekday-vs-weekend")
def weekday_vs_weekend(email: str):
    import pandas as pd

    # Load the data
    df = get_expenses_df(email)

    # 🧹 Clean the data
    df = df.dropna(subset=["Date", "Amount"])
    df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, errors='coerce')
    df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
    df = df.dropna(subset=["Amount", "Date"])

    # ➕ Add weekday/weekend info
    df["DayType"] = df["Date"].dt.weekday.apply(lambda x: "weekend" if x >= 5 else "weekday")

    # 🧮 Group by day type for total and average
    total_spending = df.groupby("DayType")["Amount"].sum().to_dict()
    avg_spending = df.groupby("DayType")["Amount"].mean().to_dict()

    # ✅ Prepare result safely
    result = {
        "weekday": {
            "total": round(total_spending.get("weekday", 0), 2),
            "average": round(avg_spending.get("weekday", 0), 2),
        },
        "weekend": {
            "total": round(total_spending.get("weekend", 0), 2),
            "average": round(avg_spending.get("weekend", 0), 2),
        },
    }

    return result


@router.get("/analytics/predictions")
def predictions(email: str):
    df = get_expenses_df(email)
    df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, errors='coerce')
    df = df.dropna(subset=["Date"])

    df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
    df = df.dropna(subset=["Amount"])
    df = df[df["Amount"] > 0]  # ✅ Filter out negative/zero


    df["Month"] = df["Date"].dt.to_period("M").astype(str)

    last_months = sorted(df["Month"].unique())
    print("🗓️ Months found:", last_months)

    if len(last_months) < 2:
        return []

    df_filtered = df[df["Month"].isin(last_months[-2:])]
    pivot = df_filtered.pivot_table(index="Category", columns="Month", values="Amount", aggfunc="sum", fill_value=0)

    # 💡 Ensure all values are float (even if they were accidentally strings)
    pivot = pivot.astype(float)

    print("📊 Pivot Table:\n", pivot)

    pivot["Predicted"] = pivot.iloc[:, -1] + (pivot.iloc[:, -1] - pivot.iloc[:, -2])
    pivot["Actual"] = pivot.iloc[:, -1]

    return [
        {
            "category": idx,
            "actual": row["Actual"],
            "predicted": row["Predicted"]
        }
        for idx, row in pivot.iterrows()
    ]


@router.get("/analytics/biggest-category")
def biggest_category(email: str):
    df = get_expenses_df(email)
    df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
    df = df.dropna(subset=["Amount"])
    top = df.groupby("Category")["Amount"].sum().sort_values(ascending=False).head(1)
    return {"category": top.index[0], "amount": top.values[0]}


@router.get("/analytics/weekly-trend")
def weekly_trend(email: str):
    df = get_expenses_df(email)  # 🔁 Pull only this user's data from MongoDB

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
    df = df.dropna(subset=["Date", "Amount"])
    
    # Group by ISO week
    df["Week"] = df["Date"].dt.to_period("W").astype(str)
    weekly = df.groupby("Week")["Amount"].sum().reset_index()
    
    return [
        {"week": row["Week"], "spending": round(row["Amount"], 2)}
        for _, row in weekly.iterrows()
    ]

@router.get("/analytics/spending-spike")
def spending_spike(email: str):
    df = get_expenses_df(email)
    
    # 🧹 Clean the data
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce", dayfirst=True)
    df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
    df = df.dropna(subset=["Date", "Amount"])

    if df.empty:
        return {"message": "No valid data available."}

    # 📆 Get latest month (accurate!)
    df["Month"] = df["Date"].dt.to_period("M")
    latest_month = df["Month"].max()
    print("🗓️ Latest month detected:", latest_month)

    df = df[df["Month"] == latest_month]
    if df.empty:
        return {"message": "No data in the latest month."}

    # 📊 Find the actual highest-spending date in that month
    day_totals = df.groupby("Date")["Amount"].sum()
    spike_date = day_totals.idxmax()
    spike_amount = day_totals.max()

    # 📦 Get all spending items from that date
    spike_items = df[df["Date"] == spike_date]

    items = [
        {
            "description": row["Description"],
            "amount": round(row["Amount"], 2),
            "category": row["Category"]
        }
        for _, row in spike_items.iterrows()
    ]

    return {
        "spike_date": spike_date.strftime("%Y-%m-%d"),
        "total_amount": round(spike_amount, 2),
        "items": items
    }

def summarize_expense_insights(analytics):
    summaries = []

    # Rule 1: Biggest category
    biggest = analytics.get("biggest_category")
    if biggest and biggest["amount"] > 0:
        summaries.append(f"High {biggest['category'].lower()} spending")

    # Rule 2: Weekday vs Weekend
    w = analytics.get("weekday_vs_weekend", {})
    if w:
        if w["weekend"]["average"] > w["weekday"]["average"] * 1.3:
            summaries.append("Weekend spending spikes")
        elif w["weekday"]["average"] > w["weekend"]["average"] * 1.3:
            summaries.append("Weekday spending spikes")

    # Rule 3: Prediction overspending
    for pred in analytics.get("predictions", []):
        if pred["predicted"] > pred["actual"] * 1.3:
            summaries.append(f"{pred['category']} overspending predicted")

    # Rule 4: Spending spike
    spike = analytics.get("spending_spike")
    if spike:
        day = spike["spike_date"]
        summaries.append(f"Spending spike on {day}")

    return summaries[:3]  # Max 3 phrases (short)

@router.get("/analytics/summary")
def summary(email: str):
    all_data = {
        "biggest_category": biggest_category(email),
        "weekday_vs_weekend": weekday_vs_weekend(email),
        "predictions": predictions(email),
        "spending_spike": spending_spike(email)
    }

    phrases = summarize_expense_insights(all_data)

    return {
        "summary_phrases": phrases,
        "raw_analytics": all_data
    }
