import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")


@dataclass
class Settings:
    alibaba_base_url: str = os.getenv(
        "ALIBABA_BASE_URL",
        "https://ws-217y1bpliyzcf5nl.ap-southeast-1.maas.aliyuncs.com",
    )
    alibaba_api_key: str = os.getenv("ALIBABA_API_KEY", "")
    sie_base_url: str = os.getenv("SIE_BASE_URL", "http://localhost:8080")
    db_path: str = os.getenv("DB_PATH", "notetaker.db")
    # default everything to cloud (verified); Task 8 flips primitives to sie
    providers: dict = field(
        default_factory=lambda: {
            "transcribe": os.getenv("PROVIDER_TRANSCRIBE", "cloud"),
            "notes": os.getenv("PROVIDER_NOTES", "cloud"),
            "extract": os.getenv("PROVIDER_EXTRACT", "cloud"),
            "embed": os.getenv("PROVIDER_EMBED", "cloud"),
            "rerank": os.getenv("PROVIDER_RERANK", "cloud"),
        }
    )


settings = Settings()
