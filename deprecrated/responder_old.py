import os
import requests
import openai
import datetime
import json
import pytz
from dotenv import load_dotenv

# Load .env variables
load_dotenv()
PAGE_ID = os.getenv("FB_PAGE_ID")
PAGE_ACCESS_TOKEN = os.getenv("FB_PAGE_ACCESS_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

BASE_FB_URL = "https://graph.facebook.com/v22.0"

# Load client config
with open("client_config.json", "r") as f:
    client_config = json.load(f)


def within_working_hours():
    tz = pytz.timezone(client_config["timezone"])
    now = datetime.datetime.now(tz)
    start = client_config["working_hours"]["start"]
    end = client_config["working_hours"]["end"]
    return start <= now.hour < end


def get_timestamp_five_minutes_ago():
    dt = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=5)
    return dt.isoformat()


def get_recent_comments():
    url = f"{BASE_FB_URL}/{PAGE_ID}/feed?fields=comments{{id,message,from,created_time}}&access_token={PAGE_ACCESS_TOKEN}"
    resp = requests.get(url)
    data = resp.json()
    recent_comments = []
    cutoff = get_timestamp_five_minutes_ago()
    for post in data.get("data", []):
        for comment in post.get("comments", {}).get("data", []):
            if comment["created_time"] > cutoff:
                recent_comments.append(comment)
    return recent_comments


def get_recent_dms():
    url = f"{BASE_FB_URL}/{PAGE_ID}/conversations?fields=messages{{id,message,from,created_time}}&access_token={PAGE_ACCESS_TOKEN}"
    resp = requests.get(url)
    data = resp.json()
    recent_messages = []
    cutoff = get_timestamp_five_minutes_ago()
    for convo in data.get("data", []):
        for msg in convo.get("messages", {}).get("data", []):
            if msg["created_time"] > cutoff:
                recent_messages.append({"id": msg["id"], "message": msg["message"], "from": msg["from"], "conversation_id": convo["id"]})
    return recent_messages


def should_respond(text):
    prompt = f"""
    Determine if the following message deserves a response from the brand. Respond only with \"yes\" or \"no\".
    Message: \"{text}\"
    """
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "system", "content": "You are a helpful assistant that decides whether to respond to social media comments."},
                  {"role": "user", "content": prompt}]
    )
    return "yes" in response.choices[0].message.content.lower()


def generate_response(text):
    prompt = f"""
    A user left the following comment or message on our social media:
    \"{text}\"
    Generate a short, {client_config["reply_style"]} brand response.

    Brand context:
    {client_config.get("response_prompt", "You are a social media assistant.")}
    """
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "system", "content": client_config.get("response_prompt", "You are a social media assistant.")},
                  {"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()


def send_comment_reply(comment_id, reply_text):
    url = f"{BASE_FB_URL}/{comment_id}/comments"
    payload = {"message": reply_text, "access_token": PAGE_ACCESS_TOKEN}
    return requests.post(url, data=payload)


def send_dm_reply(convo_id, reply_text):
    url = f"{BASE_FB_URL}/{convo_id}/messages"
    payload = {"message": reply_text, "access_token": PAGE_ACCESS_TOKEN}
    return requests.post(url, data=payload)


def main():
    if not client_config.get("auto_reply_enabled", False):
        print("Auto-reply is disabled in config.")
        return
    if not within_working_hours():
        print("Outside configured working hours. No replies sent.")
        return

    comments = get_recent_comments()
    dms = get_recent_dms()

    for comment in comments:
        text = comment["message"]
        if should_respond(text):
            reply = generate_response(text)
            send_comment_reply(comment["id"], reply)
            print(f"Replied to comment: {text}")

    for dm in dms:
        text = dm["message"]
        if should_respond(text):
            reply = generate_response(text)
            send_dm_reply(dm["conversation_id"], reply)
            print(f"Replied to DM: {text}")


if __name__ == "__main__":
    main()
