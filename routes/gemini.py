from fastapi import APIRouter
import google.generativeai as genai
from routes.analytics import summarize_expense_insights
from routes.analytics import (
    biggest_category,
    weekday_vs_weekend,
    predictions,
    spending_spike
)
from dotenv import load_dotenv
import os

# Load the .env file
load_dotenv()

# Get API key from environment variable
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

router = APIRouter()

@router.get("/profile/summary")
def profile_summary():
    all_data = {
        "biggest_category": biggest_category(),
        "weekday_vs_weekend": weekday_vs_weekend(),
        "predictions": predictions(),
        "spending_spike": spending_spike()
    }

    summary_phrases = summarize_expense_insights(all_data)

    prompt = (
        "Give savings tips based on these personal expense patterns in 3 bullet points:\n"
        f"{summary_phrases}"
    )

    model = genai.GenerativeModel("gemini-pro")
    response = model.generate_content(prompt)

    return {
        "summary_phrases": summary_phrases,
        "gemini_tips": response.text
    }
