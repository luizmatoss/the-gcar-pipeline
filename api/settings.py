from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
LOG_DIR = DATA_DIR / "logs"

RAW_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_URL = "https://www.green.car/audi/e-tron-gt/saloon-electric"

REQUIRED_SECTIONS = [
    "Interior Features",
    "Entertainment",
    "Driver Convenience",
    "Security",
    "Exterior Features",
    "Passive Safety",
    "Wheels",
    "Engine/Drivetrain/Suspension",
]
