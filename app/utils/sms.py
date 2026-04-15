import requests
import os

FAST2SMS_API_KEY = os.getenv("FAST2SMS_API_KEY")


def send_sms(phone: str, message: str):
    if not FAST2SMS_API_KEY:
        raise Exception("Missing FAST2SMS API KEY")

    url = "https://www.fast2sms.com/dev/bulkV2"

    headers = {
        "authorization": FAST2SMS_API_KEY,
        "Content-Type": "application/json"
    }

    payload = {
        "route": "q",
        "message": message,
        "language": "english",
        "numbers": phone.replace("+91", "")
    }

    res = requests.post(url, headers=headers, json=payload)

    if res.status_code != 200:
        raise Exception(f"SMS failed: {res.text}")