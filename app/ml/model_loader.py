import os
import requests
import joblib
import io

_pipeline = None
_threshold = None


def load_from_url(url: str):
    if not url:
        raise RuntimeError("URL not set")

    response = requests.get(url)
    response.raise_for_status()

    # safety check
    if b"<html" in response.content[:200].lower():
        raise RuntimeError("Downloaded HTML instead of model")

    return joblib.load(io.BytesIO(response.content))


def get_pipeline():
    global _pipeline

    if _pipeline is None:
        _pipeline = load_from_url(os.getenv("PIPELINE_URL"))

    return _pipeline


def get_threshold():
    global _threshold

    if _threshold is None:
        _threshold = load_from_url(os.getenv("THRESHOLD_URL"))

    return _threshold