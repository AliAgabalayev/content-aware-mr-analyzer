import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    gitlab_webhook_secret: str
    leantime_url: str
    leantime_api_key: str
    leantime_done_status: str
    discord_webhook_url: str


@lru_cache
def get_settings() -> Settings:
    return Settings(
        gitlab_webhook_secret=os.environ["GITLAB_WEBHOOK_SECRET"],
        leantime_url=os.environ["LEANTIME_URL"],
        leantime_api_key=os.environ["LEANTIME_API_KEY"],
        leantime_done_status=os.environ.get("LEANTIME_DONE_STATUS", "done"),
        discord_webhook_url=os.environ["DISCORD_WEBHOOK_URL"],
    )
