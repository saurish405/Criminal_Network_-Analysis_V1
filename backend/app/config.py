import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

APP_TITLE = "NCRB Crime Intelligence Core"
APP_DESCRIPTION = "AI-Powered Criminal Network Analysis & BSA Section 63 Evidence Engine"
APP_VERSION = "1.0.0"
HOST = "0.0.0.0"
PORT = 8000