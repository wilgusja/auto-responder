"""
This script generates configuration files for the autoresponder system based on data from a Google Sheet.
It connects to the Google Sheets API, retrieves the data, and formats it into JSON files for each business.
It also formats the brand context using OpenAI's API to ensure the data is structured correctly.
"""

import gspread
from google.oauth2.service_account import Credentials
import json
import os
from format_brand_context import format_brand_context

# Load credentials and connect to the Sheet
creds = Credentials.from_service_account_file("service_account.json", scopes=[
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
])
client = gspread.authorize(creds)

# Open the Sheet by name (could also use open_by_key if needed)
sheet = client.open("Autoresponder Onboarding").sheet1
records = sheet.get_all_records()

# Make sure output folder exists
os.makedirs("configs", exist_ok=True)

# Convert each row into a config JSON file
for record in records:
    if not record.get("Business Name"):
        continue  # Skip empty rows

    name = record["Business Name"].strip().lower().replace(" ", "_")

    raw_context = record.get("Brand Context (Raw)", "").strip()
    structured_prompt = format_brand_context(raw_context) if raw_context else ""

    config = {
        "brand_name": record["Business Name"],
        "timezone": record["Time Zone"],
        "working_hours": {
            "start": int(record["Start Hour"]),
            "end": int(record["End Hour"])
        },
        "page_ids": {
            "facebook": str(record.get("Facebook Page ID", "")).strip(),
            "instagram": str(record.get("Instagram Business ID", "")).strip()
        },
        "page_access_token": record.get("Page Access Token", "").strip(),
        "reply_style": record["Brand Voice"],
        "response_prompt": structured_prompt,
        "auto_reply_enabled": record.get("Enable Auto Reply", "yes").strip().lower() == "yes",
        "platforms": {
            "facebook": "Facebook" in record.get("Platforms", ""),
            "instagram": "Instagram" in record.get("Platforms", "")
        },
        "filters": {
            "require_question": record.get("Only Respond to Questions?", "no").strip().lower() == "yes",
            "ignored_keywords": [kw.strip() for kw in record.get("Ignored Keywords", "").split(",") if kw.strip()]
        }
    }

    filepath = f"configs/{name}_config.json"
    with open(filepath, "w") as f:
        json.dump(config, f, indent=2)

    print(f"✅ Saved config: {filepath}")
