import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = BASE_DIR / "models"
MODEL_DIR.mkdir(exist_ok=True)

load_dotenv(BASE_DIR / ".env")

MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "123456")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "water_leak_system")
MYSQL_CHARSET = os.getenv("MYSQL_CHARSET", "utf8mb4")

MODEL_PATH = MODEL_DIR / "leak_model.pkl"
METRICS_PATH = MODEL_DIR / "metrics.json"

LEAK_THRESHOLD = 12.0

FEATURE_COLUMNS = [
    "instant_usage",
    "node_inflow",
    "node_outflow",
    "leakage_rate",
    "pressure",
    "hour",
    "day_of_week",
    "meter_age_days",
]
