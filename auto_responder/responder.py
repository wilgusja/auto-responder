import os
import requests
import datetime
import json
import pytz
import argparse
from dotenv import load_dotenv
from openai import OpenAI
from functools import lru_cache
from auto_responder.comment_store import (
    init_comment_db, log_post, log_comment,
    mark_comment_as_responded, get_recent_post_comments
)

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

BASE_FB_URL = "https://graph.facebook.com/v22.0"
CONFIG_FOLDER = "configs"
LOG_FOLDER = "logs"
LOG_FILE = os.path.join(LOG_FOLDER, "responder_comments.log")


def load_all_client_configs():
    configs = []
    for filename in os.listdir(CONFIG_FOLDER):
        if filename.endswith("_config.json"):
            with open(os.path.join(CONFIG_FOLDER, filename), "r") as f:
                config = json.load(f)
                configs.append(config)
    return configs

all_client_configs = load_all_client_configs()


@lru_cache(maxsize=None)  # Cache to avoid reloading configs
def within_working_hours(client_config_json):
    client_config = json.loads(client_config_json)
    tz = pytz.timezone(client_config["timezone"])
    now = datetime.datetime.now(tz)
    start = client_config["working_hours"]["start"]
    end = client_config["working_hours"]["end"]
    return start <= now.hour < end


def get_recent_comments(page_id, page_access_token, brand_name, verbose=False):
    url = f"{BASE_FB_URL}/{page_id}/feed?fields=comments{{id,message,from,created_time,parent}}&access_token={page_access_token}"
    resp = requests.get(url)
    data = resp.json()
    recent_comments = []
    cutoff = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=5)).isoformat()
    for post in data.get("data", []):
        log_post(post["id"], page_id, brand_name, post.get("created_time", datetime.datetime.utcnow().isoformat()))
        for comment in post.get("comments", {}).get("data", []):
            if comment["created_time"] > cutoff:
                recent_comments.append({
                    "id": comment["id"],
                    "message": comment.get("message", ""),
                    "from": comment.get("from", {}).get("id"),
                    "created_time": comment["created_time"],
                    "post_id": post["id"]
                })
    if verbose:
        print(f"Retrieved {len(recent_comments)} recent comments for Page ID: {page_id}")
    return recent_comments


def kick_to_slack(message):
    webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    if not webhook_url:
        print("SLACK_WEBHOOK_URL not set")
        return

    payload = {
        "text": message
    }

    response = requests.post(webhook_url, json=payload)
    if response.status_code != 200:
        print(f"Error sending message to Slack: {response.status_code} {response.text}")


@lru_cache(maxsize=1000)
def should_respond(comment_text, client_config_json):
    client_config = json.loads(client_config_json)
    comment_text_lower = comment_text.lower()
    filters = client_config.get("filters", {})
    if any(bad in comment_text_lower for bad in filters.get("ignored_keywords", [])):
        print(f"❌ Ignoring comment due to keyword filter: {comment_text}")
        return False
    if filters.get("require_question", False) and not comment_text.strip().endswith("?"):
        print(f"❌ Skipping non-question comment: {comment_text}")
        return False

    prompt = f"Should the brand respond to this comment? Only answer yes or no:\n\n\"{comment_text}\""
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that decides whether to respond to public comments on social media posts."},
                {"role": "user", "content": prompt}
            ]
        )
        reply = response.choices[0].message.content.strip()
        print(f"🧐 Comment: {comment_text}\n🤖 Model reply: {reply}\n")
        return "yes" in reply.lower()
    except Exception as e:
        print(f"OpenAI error: {e}")
        return False


def generate_comment_reply(comment_text, client_config):
    prompt = f"Respond to the following comment in a {client_config['reply_style']} tone:\n\n{comment_text}"
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": client_config.get("response_prompt", "You are a helpful social media assistant.")},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content.strip()


def post_comment_reply(comment_id, reply_text, page_access_token):
    url = f"{BASE_FB_URL}/{comment_id}/comments"
    payload = {"message": reply_text, "access_token": page_access_token}
    resp = requests.post(url, data=payload)
    print(f"Post comment reply response: {resp.status_code} {resp.text}")
    return resp


def log_comment(brand, incoming_text, reply_text):
    os.makedirs(LOG_FOLDER, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    with open(LOG_FILE, "a") as f:
        f.write(f"{timestamp} [{brand}]\n")
        f.write(f"> {incoming_text}\n")
        f.write(f"→ {reply_text}\n\n")


# Main function to poll comments and respond
def main(dry_run=False, verbose=False):
    """
    Main function to poll recent comments and respond using OpenAI.

    Parameters:
        dry_run (bool): If True, preview replies without posting them.
        verbose (bool): If True, print detailed information about the process.
    """
    init_comment_db()  # Ensure the database is initialized

    for client_config in all_client_configs:
        process_client(client_config, dry_run, verbose)


def process_client(client_config, dry_run, verbose):
    """
    Process a single client configuration to fetch comments and respond.

    Parameters:
            print(f"[SKIP] Skipping {client_config['brand_name']} — auto-reply disabled.")
        dry_run (bool): If True, preview replies without posting them.
        verbose (bool): If True, print detailed information about the process.
    """
    if not client_config.get("auto_reply_enabled", False):
        print(f"Skipping {client_config['brand_name']} — auto-reply disabled.")
        return

    if not within_working_hours(json.dumps(client_config)):
        print(f"Skipping {client_config['brand_name']} — outside working hours.")
        return

    page_id = client_config["page_ids"].get("facebook")
    page_access_token = client_config.get("page_access_token")

    if not page_id or not page_access_token:
        print(f"Skipping {client_config['brand_name']} — missing Page ID or Access Token.")
        return

    comments = fetch_comments(page_id, page_access_token, client_config['brand_name'], verbose)
    handle_comments(comments, client_config, dry_run, page_access_token)


def fetch_comments(page_id, page_access_token, brand_name, verbose):
    """
    Fetch recent comments for a Facebook page.

    Parameters:
        page_id (str): Facebook Page ID.
        page_access_token (str): Access token for the page.
        brand_name (str): Name of the brand.
        verbose (bool): If True, print detailed information.

    Returns:
        list: List of recent comments.
    """
    return get_recent_comments(page_id, page_access_token, brand_name, verbose)


def handle_comments(comments, client_config, dry_run, page_access_token):
    """
    Handle comments by generating and posting replies.

    Parameters:
        comments (list): List of comments to process.
        client_config (dict): Configuration for the client.
        dry_run (bool): If True, preview replies without posting them.
        page_access_token (str): Access token for the page.
    """
    for comment in comments:
        process_comment(comment, client_config, dry_run, page_access_token)


def process_comment(comment, client_config, dry_run, page_access_token):
    """
    Process a single comment by generating and posting a reply.

    Parameters:
        comment (dict): Comment data.
        client_config (dict): Configuration for the client.
        dry_run (bool): If True, preview replies without posting them.
        page_access_token (str): Access token for the page.
    """
    comment_id = comment["id"]
    comment_text = comment["message"]
    brand_name = client_config['brand_name']

    log_comment(brand_name, comment_text, "")  # Log incoming comment without reply

    reply = generate_comment_reply(comment_text, client_config)
    if not reply.strip():
        print(f"[{brand_name}] Skipping reply due to empty or invalid response.")
        return

    if dry_run:
        print(f"[DRY RUN] Reply for comment ID {comment_id}: {reply}")
    else:
        response = post_comment_reply(comment_id, reply, page_access_token)
        if response.status_code == 200:
            mark_comment_as_responded(comment_id)
        print(f"[{brand_name}] Replied to comment: {comment_text}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Poll recent comments and respond using OpenAI.")
    parser.add_argument("--dry-run", action="store_true", help="Preview replies without posting them.")
    parser.add_argument("--verbose", action="store_true", help="Print number of comments found per client.")
    args = parser.parse_args()
    main(dry_run=args.dry_run, verbose=args.verbose)
