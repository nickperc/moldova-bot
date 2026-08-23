from datetime import datetime
from zoneinfo import ZoneInfo

CHISINAU_TZ = ZoneInfo("Europe/Chisinau")


def now_chisinau() -> datetime:
    return datetime.now(CHISINAU_TZ)
