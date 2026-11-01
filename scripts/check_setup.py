"""Check that the keys in .env work, and fill in TELEGRAM_CHAT_ID.

Run from the project folder:  python3 scripts/check_setup.py
Prints pass/fail only. It never prints a key.
"""
import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kickoff.envfile import load_env, set_env_value  # noqa: E402

load_env()


def get_json(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.load(resp)


def check_anthropic():
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        print("FAIL  ANTHROPIC_API_KEY is empty in .env")
        return
    try:
        data = get_json("https://api.anthropic.com/v1/models",
                        {"x-api-key": key, "anthropic-version": "2023-06-01"})
        print(f"PASS  Anthropic key works ({len(data.get('data', []))} models visible)")
    except urllib.error.HTTPError as e:
        print(f"FAIL  Anthropic key rejected (HTTP {e.code})")
    except Exception as e:
        print(f"FAIL  Could not reach Anthropic: {type(e).__name__}")


def check_telegram():
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        print("FAIL  TELEGRAM_BOT_TOKEN is empty in .env")
        return
    base = f"https://api.telegram.org/bot{token}"
    try:
        me = get_json(f"{base}/getMe")["result"]
        print(f"PASS  Telegram token works (bot: @{me['username']})")
    except urllib.error.HTTPError as e:
        print(f"FAIL  Telegram token rejected (HTTP {e.code})")
        return
    except Exception as e:
        print(f"FAIL  Could not reach Telegram: {type(e).__name__}")
        return

    if os.environ.get("TELEGRAM_CHAT_ID"):
        print("PASS  TELEGRAM_CHAT_ID is already set")
        return
    updates = get_json(f"{base}/getUpdates")["result"]
    chats = [u["message"]["chat"] for u in updates
             if "message" in u and u["message"]["chat"].get("type") == "private"]
    if not chats:
        print("FAIL  No message found. Open your bot in Telegram, send it 'hi', run this again.")
        return
    chat_id = str(chats[-1]["id"])
    set_env_value("TELEGRAM_CHAT_ID", chat_id)
    print(f"PASS  Found your chat ID ({chat_id}) and saved it to .env")


def check_football_data():
    key = os.environ.get("FOOTBALL_DATA_API_KEY", "")
    if not key:
        print("FAIL  FOOTBALL_DATA_API_KEY is empty in .env")
        return
    try:
        data = get_json("https://api.football-data.org/v4/competitions", {"X-Auth-Token": key})
        print(f"PASS  football-data.org key works ({data.get('count', '?')} competitions on your plan)")
    except urllib.error.HTTPError as e:
        print(f"FAIL  football-data.org key rejected (HTTP {e.code})")
    except Exception as e:
        print(f"FAIL  Could not reach football-data.org: {type(e).__name__}")


def check_api_football():
    key = os.environ.get("API_FOOTBALL_KEY", "")
    if not key:
        print("FAIL  API_FOOTBALL_KEY is empty in .env")
        return
    try:
        data = get_json("https://v3.football.api-sports.io/status", {"x-apisports-key": key})
        if data.get("errors"):
            print("FAIL  API-Football key rejected")
            return
        info = data["response"]
        print(f"PASS  API-Football key works (plan: {info['subscription']['plan']}, "
              f"{info['requests']['current']} of {info['requests']['limit_day']} requests used today)")
    except urllib.error.HTTPError as e:
        print(f"FAIL  API-Football key rejected (HTTP {e.code})")
    except Exception as e:
        print(f"FAIL  Could not reach API-Football: {type(e).__name__}")


check_anthropic()
check_telegram()
check_football_data()
check_api_football()
