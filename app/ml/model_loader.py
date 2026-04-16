import os
import joblib
import requests
import logging

logger = logging.getLogger(__name__)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PIPELINE_PATH = os.path.join(BASE_DIR, "ml", "fraud_pipeline.pkl")

PIPELINE_URL = os.getenv("PIPELINE_URL")

pipeline = None
MODEL_LOADED = False


def download_file(url, path):
    if not url:
        logger.warning("PIPELINE_URL not set")
        return

    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)

        try:
            r = requests.get(url, timeout=10)
            r.raise_for_status()

            with open(path, "wb") as f:
                f.write(r.content)

            logger.info("Model downloaded successfully")

        except Exception as e:
            logger.error(f"Download failed: {e}")


def load_model():
    global pipeline, MODEL_LOADED

    try:
        download_file(PIPELINE_URL, PIPELINE_PATH)
        pipeline = joblib.load(PIPELINE_PATH)
        MODEL_LOADED = True
        logger.info("ML pipeline loaded successfully")

    except Exception as e:
        logger.error(f"Model load failed: {e}")
        MODEL_LOADED = False


def get_pipeline():
    if not MODEL_LOADED:
        load_model()

    if pipeline is None:
        raise RuntimeError("ML model not loaded")

    return pipeline