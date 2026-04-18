import requests, joblib, io

# PIPELINE
p_url = "https://drive.google.com/uc?export=download&id=1TeY_JUSJuWwFkhRldwVNkg296tO3d-Hz"
pipeline = joblib.load(io.BytesIO(requests.get(p_url).content))
print("PIPELINE OK:", pipeline.feature_names_in_)

# THRESHOLD
t_url = "https://drive.google.com/uc?export=download&id=1frJWEeeeFgbahpF-SonudDNPJ7GkpH7n"
threshold = joblib.load(io.BytesIO(requests.get(t_url).content))
print("THRESHOLD OK:", threshold)