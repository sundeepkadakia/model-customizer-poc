import runpod
import os
from pathlib import Path
from dotenv import load_dotenv

ENV_FILE = Path(__file__).resolve().parent / ".env"

print("Looking for:", ENV_FILE)
print("Exists:", ENV_FILE.exists())

loaded = load_dotenv(ENV_FILE, override=True)

print("load_dotenv returned:", loaded)
print("RUNPOD_API_KEY present:", "RUNPOD_API_KEY" in os.environ)
print("RUNPOD_API_KEY non-empty:", bool(os.getenv("RUNPOD_API_KEY")))

RUNPOD_API_KEY = os.getenv("RUNPOD_API_KEY")

if not RUNPOD_API_KEY:
    raise RuntimeError("RUNPOD_API_KEY is not configured")

runpod.api_key = RUNPOD_API_KEY

print("Connected!")