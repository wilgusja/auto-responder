# This script fetches the pages associated with a user's access token and exchanges the short-lived page access tokens for long-lived ones.
# This is useful for applications that need to maintain access to Facebook pages over a longer period without requiring the user to re-authenticate frequently.
# It uses the Facebook Graph API to fetch the pages and their access tokens, and then exchanges the short-lived tokens for long-lived ones.

import os
import requests
import json
import argparse
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(override=True)

USER_ACCESS_TOKEN = os.getenv("FB_USER_ACCESS_TOKEN")
APP_ID = os.getenv("APP_ID")
APP_SECRET = os.getenv("APP_SECRET")
GRAPH_URL = "https://graph.facebook.com/v22.0"
CONFIG_FOLDER = "configs"
LOG_FILE = "logs/generate_page_token.log"

if not USER_ACCESS_TOKEN:
    raise EnvironmentError("FB_USER_ACCESS_TOKEN environment variable is not set. Please set it in your .env file or environment.")

if not APP_ID:
    raise EnvironmentError("APP_ID environment variable is not set. Please set it in your .env file or environment.")

if not APP_SECRET:
    raise EnvironmentError("APP_SECRET environment variable is not set. Please set it in your .env file or environment.")


def get_pages():
    """
    Fetch the list of Facebook pages associated with the user's access token.

    Returns:
        list: A list of page data dictionaries, or an empty list if an error occurs.
    """
    url = f"{GRAPH_URL}/me/accounts?access_token={USER_ACCESS_TOKEN}"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        print(f"Error fetching pages: {e}")
        return []
    except ValueError:
        print("Error decoding JSON response from Facebook API.")
        return []
    return data.get("data", [])


def exchange_for_long_lived_token(short_token):
    """
    Exchange a short-lived Facebook page access token for a long-lived token using the Graph API.

    Args:
        short_token (str): The short-lived page access token.

    Returns:
        str or None: The long-lived access token if successful, otherwise None.
    """
    url = f"{GRAPH_URL}/oauth/access_token"
    params = {
        "grant_type": "fb_exchange_token",
        "client_id": APP_ID,
        "client_secret": APP_SECRET,
        "fb_exchange_token": short_token
    }
    params = {
        "grant_type": "fb_exchange_token",
        "client_id": APP_ID,
        "client_secret": APP_SECRET,
        "fb_exchange_token": short_token
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if "access_token" in data:
            return data["access_token"]
        else:
            print(f"Error: 'access_token' not found in response: {data}")
            return None
    except requests.RequestException as e:
        print(f"HTTP request failed: {e}")
        return None
    except ValueError:
        print("Error decoding JSON response.")
        return None


def log_update(message):
    """
    Append a log message with a timestamp to the log file.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}\n"
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "a") as log_file:
            log_file.write(log_entry)
    except Exception as e:
        print(f"Failed to write to log file: {e}")


def update_config_with_token(page_id, long_token, dry_run=False):
    """
    Update the config file for the given page_id with the new long-lived token.
    If dry_run is True, do not write changes to disk.
    """
    if not os.path.isdir(CONFIG_FOLDER):
        print(f"⚠️ Config folder '{CONFIG_FOLDER}' does not exist. Token NOT saved.")
        return
    for filename in os.listdir(CONFIG_FOLDER):
        if filename.endswith("_config.json"):
            filepath = os.path.join(CONFIG_FOLDER, filename)
            try:
                with open(filepath, "r") as f:
                    config = json.load(f)
            except (IOError, OSError, json.JSONDecodeError) as e:
                print(f"Error reading or parsing {filepath}: {e}")
                continue

            if config.get("page_ids", {}).get("facebook") == page_id:
                config["page_access_token"] = long_token
                if not dry_run:
                    try:
                        with open(filepath, "w") as f:
                            json.dump(config, f, indent=2)
                        print(f"✅ Updated config for {config['brand_name']} with new Page Access Token.")
                        log_update(f"Updated config for {config['brand_name']} (Page ID: {page_id})")
                    except (IOError, OSError) as e:
                        print(f"❌ Failed to write updated config for {config['brand_name']} (Page ID: {page_id}): {e}")
                else:
                    print(f"[DRY RUN] Would update config for {config['brand_name']} (Page ID: {page_id})")
                return
    print(f"⚠️ No matching config found for Page ID {page_id}. Token NOT saved.")
    return


def main():
    parser = argparse.ArgumentParser(description="Generate and assign long-lived Page Access Tokens.")
    parser.add_argument("--dry-run", action="store_true", help="Do not write changes to disk.")
    args = parser.parse_args()
    dry_run = args.dry_run

    pages = get_pages()
    if not pages:
        print("No pages found or failed to fetch pages.")
        return

    for page in pages:
        name = page.get("name")
        page_id = page.get("id")
        short_token = page.get("access_token")
        print("\n---")
        print(f"Page: {name}")
        print(f"Page ID: {page_id}")

        if not short_token:
            print("❌ No short-lived access token found for this page.")
            continue

        long_token = exchange_for_long_lived_token(short_token)
        if long_token:
            print(f"✅ Long-Lived Page Access Token generated: ...{long_token[-10:]}")
            update_config_with_token(page_id, long_token, dry_run)
        else:
            print("❌ Failed to generate long-lived token.")


if __name__ == "__main__":
    main()
