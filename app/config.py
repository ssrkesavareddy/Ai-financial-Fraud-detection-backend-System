from dotenv import load_dotenv
import os

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
BASE_URL = os.getenv("BASE_URL")
if not SECRET_KEY:
    raise Exception("SECRET_KEY missing")

SECURITY_QUESTIONS = [
    "What is your favorite actor?",
    "What was your first school name?",
    "What is your favorite movie?",
    "What is your childhood nickname?"
]