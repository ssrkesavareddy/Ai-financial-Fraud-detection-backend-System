from dotenv import load_dotenv
import os

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
BASE_URL = os.getenv("BASE_URL")

if not SECRET_KEY:
    raise RuntimeError("FATAL: SECRET_KEY environment variable is not set.")

if not BASE_URL:
    raise RuntimeError("FATAL: BASE_URL environment variable is not set.")


