import os
import requests
import datetime
import json
import pytz
import argparse
from collections import defaultdict
from dotenv import load_dotenv
from openai import OpenAI
from deprecrated.conversation_store import init_db, log_message, get_recent_user_messages, mark_as_responded

# Load .env variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

BASE_FB_URL = "https://graph.facebook.com/v22.0"
CONFIG_FOLDER = "configs"
LOG_FOLDER = "logs"
LOG_FILE = os.path.join(LOG_FOLDER, "responder_dryrun.log")

# Load all client configs
def load_all_client_configs():
    configs = []
    for filename in os.listdir(CONFIG_FOLDER):
        if filename.endswith("_config.json"):
            with open(os.path.join(CONFIG_FOLDER, filename), "r") as f:
                config = json.load(f)
                configs.append(config)
    return configs

all_client_configs = load_all_client_configs()


def within_working_hours(client_config):
    tz = pytz.timezone(client_config["timezone"])
    now = datetime.datetime.now(tz)
    start = client_config["working_hours"]["start"]
    end = client_config["working_hours"]["end"]
    return start <= now.hour < end


def get_timestamp_five_minutes_ago():
    dt = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=5)
    return dt.isoformat()


def get_recent_dms(page_id, page_access_token, brand_name, verbose=False):
    url = f"{BASE_FB_URL}/{page_id}/conversations?fields=messages{{id,message,from,created_time}}&access_token={page_access_token}"
    resp = requests.get(url)
    data = resp.json()
    recent_messages = []
    cutoff = get_timestamp_five_minutes_ago()
    for convo in data.get("data", []):
        for msg in convo.get("messages", {}).get("data", []):
            if msg["created_time"] > cutoff:
                recent_messages.append({
                    "id": msg["id"],
                    "message": msg["message"],
                    "from": msg["from"],
                    "conversation_id": convo["id"],
                    "created_time": msg["created_time"]
                })
    if verbose:
        print(f"Retrieved {len(recent_messages)} recent DMs for Page ID: {page_id}")
    return recent_messages


def group_messages_by_user(dms):
    grouped = defaultdict(list)
    for msg in dms:
        user_id = msg["from"]["id"]
        grouped[user_id].append(msg)
    return grouped


def should_respond(context_messages, client_config):
    summary = "\n".join([f"User: {m}" for m in context_messages])
    prompt = f"""
    Here is the latest conversation from a user. Should we respond? Only answer with \"yes\" or \"no\".\n\n{summary}
    """
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that decides whether to respond to social media DMs."},
                {"role": "user", "content": prompt}
            ]
        )
        reply = response.choices[0].message.content.strip()
        print(f"\n🧐 Checking convo:\n{summary}\n🤖 Model replied: {reply}\n")
        return "yes" in reply.lower()
    except Exception as e:
        print(f"Error during OpenAI API call: {e}")
        return False


def generate_response(context_messages, client_config):
    summary = "\n".join([f"User: {m}" for m in context_messages])
    prompt = f"""
    This is an ongoing conversation with a customer. Based on the messages below, generate a single brand-aligned response.\n\n{summary}
    """
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": client_config.get("response_prompt", "You are a social media assistant.")},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content.strip()


def send_dm_reply(user_id, reply_text, page_access_token, page_id):
    url = f"{BASE_FB_URL}/{page_id}/messages"
    payload = {
        "recipient": {"id": user_id},
        "message": {"text": reply_text},
        "access_token": page_access_token
    }
    resp = requests.post(url, json=payload)
    print(f"Response from Meta API: {resp.status_code} {resp.text}")
    return resp


def log_dryrun(brand, incoming_text, reply_text):
    os.makedirs(LOG_FOLDER, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    with open(LOG_FILE, "a") as f:
        f.write(f"{timestamp} [{brand}]\n")
        f.write(f"> {incoming_text}\n")
        f.write(f"→ {reply_text}\n\n")


def main(dry_run=False, verbose=False):
    init_db()
    for client_config in all_client_configs:
        if not client_config.get("auto_reply_enabled", False):
            print(f"Skipping {client_config['brand_name']} — auto-reply disabled.")
            continue

        if not within_working_hours(client_config):
            print(f"Skipping {client_config['brand_name']} — outside working hours.")
            continue

        page_id = client_config["page_ids"].get("facebook")
        page_access_token = client_config.get("page_access_token")

        if not page_id or not page_access_token:
            print(f"Skipping {client_config['brand_name']} — missing Page ID or Access Token.")
            continue

        dms = get_recent_dms(page_id, page_access_token, client_config['brand_name'], verbose=verbose)
        grouped = group_messages_by_user(dms)

        for user_id, msgs in grouped.items():
            # Log new messages
            for m in msgs:
                log_message(m["id"], user_id, page_id, client_config['brand_name'], m["message"], m["created_time"])

            context = get_recent_user_messages(user_id, page_id, limit=10)
            if should_respond(context, client_config):
                reply = generate_response(context, client_config)
                if dry_run:
                    print(f"[DRY RUN][{client_config['brand_name']}] Would reply to DM:\n> {' | '.join(context)}\n→ {reply}\n")
                    log_dryrun(client_config['brand_name'], ' | '.join(context), reply)
                else:
                    send_dm_reply(user_id, reply, page_access_token, page_id)
                    print(f"[{client_config['brand_name']}] Replied to DM thread with {len(context)} messages")
                    for m in msgs:
                        mark_as_responded(m["id"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Poll recent DMs and respond using OpenAI.")
    parser.add_argument("--dry-run", action="store_true", help="Preview replies without posting them.")
    parser.add_argument("--verbose", action="store_true", help="Print number of DMs found per client.")
    args = parser.parse_args()
    main(dry_run=args.dry_run, verbose=args.verbose)
