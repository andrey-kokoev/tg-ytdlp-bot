"""
Copy this file to `CONFIG/config_secret.py` and fill in real values.

This file is intentionally safe to commit; `CONFIG/config_secret.py` should be ignored by git.
"""


class SecretConfig(object):
    # Telegram API credentials
    API_ID = 0
    API_HASH = ""

    # Bot token from @BotFather
    BOT_TOKEN = ""

    # Optional: user session string for ChannelGuard (admin log access)
    CHANNEL_GUARD_SESSION_STRING = ""

    # Optional: Firebase secrets (if USE_FIREBASE=True)
    FIREBASE_PASSWORD = "XXXXXXXXXXXXXXXxx"
    FIREBASE_CONF = {
        "apiKey": "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
        "authDomain": "XXXXXXXXXXXX.firebaseapp.com",
        "projectId": "XXXXXXXXXX-0000000000",
        "storageBucket": "XXXXXXXXXXXXXX-0000000000.firebasestorage.app",
        "messagingSenderId": "0000000000000000",
        "appId": "1:0000000000000:web:00000000000000a",
        "databaseURL": "https://XXXXXXXXXXXXXX-000000000-default-rtdb.europe-west1.firebasedatabase.app"
    }

    # Optional: proxy secrets
    PROXY_USER = ""
    PROXY_PASSWORD = ""
    PROXY_2_USER = ""
    PROXY_2_PASSWORD = ""

