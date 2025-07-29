# README

| Topic             | Simple Version                                                           |
|-------------------|--------------------------------------------------------------------------|
| User Access Token | Tied to you. One token for all private apps you run.                     |
| Page Access Token | One per client. Covers both Facebook Page and attached IG Business.      |
| Current App Setup | One client per run. Future: multi-client scaling possible.               |
| Hosting           | Either deploy multiple instances or make responder multi-client capable. |

| Field                      | Type              | Example                               | Notes                                                                               |
| -------------------------- | ----------------- | ------------------------------------- | ----------------------------------------------------------------------------------- |
| `brand_name`               | string            | `"Vitris Supplements"`                | Friendly name for logs                                                              |
| `timezone`                 | string            | `"America/New_York"`                  | [IANA timezone names](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones) |
| `working_hours.start`      | int               | `9`                                   | 24h format                                                                          |
| `working_hours.end`        | int               | `17`                                  | 24h format                                                                          |
| `page_ids.facebook`        | string            | `"450113084847701"`                   | Facebook Page ID                                                                    |
| `page_ids.instagram`       | string (optional) | `"17841412345678901"`                 | (for future use)                                                                    |
| `page_access_token`        | string            | `"EAAQl0gij8lUBO..."`                 | Unique Page Access Token per brand ✅                                                |
| `reply_style`              | string            | `"friendly"`                          | How brand replies should sound                                                      |
| `response_prompt`          | string            | `"Vitris sells Boost and Recover..."` | Background for OpenAI                                                               |
| `auto_reply_enabled`       | bool              | `true`                                | Easy on/off toggle                                                                  |
| `platforms.facebook`       | bool              | `true`                                | Whether FB polling should run                                                       |
| `platforms.instagram`      | bool              | `false`                               | For future                                                                          |
| `filters.require_question` | bool              | `false`                               | Only respond if it’s a question?                                                    |
| `filters.ignored_keywords` | list              | `["giveaway", "contest"]`             | Ignore DMs containing these words                                                   |

## How to Set Up Automod

## Step 1: Get a **User Access Token**

1. Go to the [Graph API explorer](https://developers.facebook.com/tools/explorer).
2. Choose relevant app from the 'Meta App' dropdown menu.
3. Select "User Token" from the 'User or Page' dropdown menu.
4. Click blue "Generate Access Token" button.
5. In popup window, agree to requested permissions and relevant pages.
6. Copy the generated **Access Token**.

## Step 2: Get a short-lived **Page Access Token**

After retrieving a **User Access Token** from the [Graph API explorer](https://developers.facebook.com/tools/explorer):

```bash
curl -X GET "https://graph.facebook.com/v22.0/me/accounts?access_token=$FB_USER_ACCESS_TOKEN"
```

Expected response:

```json
{
  "data": [
    {
      "access_token": "EAAQl0gij8lUBOZBKHhIGDHZC...",
      "id": "450113084847701",
      "name": "Vitris Supplements"
    }
  ]
}
```

$\rightarrow$ Short-lived **Page Access Token** is at `["data"][0]["access_token"]`  
$\rightarrow$ **Page ID** is at `["data"][0]["id"]`

## Step 3: Exchange for a long-lived **Page Access Token**

If not already saved in `.env`, the App ID and App Secret can be found on [the developer portal.](https://developers.facebook.com/apps), under App Settings > Basic. Substitute the App ID, App Secret, and short-lived Page Access Token in the following:

```bash
curl -X GET "https://graph.facebook.com/v22.0/oauth/access_token?
    grant_type=fb_exchange_token&
    client_id=$APP_ID&
    client_secret=$APP_SECRET&
    fb_exchange_token=$SHORT_LIVED_PAGE_ACCESS_TOKEN"
```

Expected response:

```json
{
  "access_token": "EAAQl0gij8lUBO...",
  "token_type": "bearer",
  "expires_in": 5184000  # ~60 days
}
```

## Step 4: Save variables to  `.env` file
