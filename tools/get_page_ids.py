"""This script retrieves the IDs of Facebook Pages managed by the user."""

import os
import requests
from dotenv import load_dotenv

# Load user access token
load_dotenv(override=True)
USER_ACCESS_TOKEN = os.getenv("FB_USER_ACCESS_TOKEN")

GRAPH_URL = "https://graph.facebook.com/v22.0"

def get_managed_pages():
    url = f"{GRAPH_URL}/me/accounts?access_token={USER_ACCESS_TOKEN}"
    resp = requests.get(url)
    data = resp.json()
    
    if "data" not in data:
        print("No pages found or invalid token.")
        print(data)
        return

    print("Your managed Pages:")
    for page in data["data"]:
        name = page.get("name")
        page_id = page.get("id")
        print(f"- {name}: {page_id}")

if __name__ == "__main__":
    get_managed_pages()
