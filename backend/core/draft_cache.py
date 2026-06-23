from datetime import datetime, timedelta
from typing import Optional

class DraftCache:
    def __init__(self):
        # Stores draft_id -> (data_dict, expiry_datetime)
        self._store: dict[str, tuple[dict, datetime]] = {}

    def set(self, draft_id: str, data: dict, ttl_minutes: int = 30):
        expiry = datetime.utcnow() + timedelta(minutes=ttl_minutes)
        self._store[draft_id] = (data, expiry)

    def get(self, draft_id: str) -> Optional[dict]:
        self._cleanup()
        entry = self._store.get(draft_id)
        if not entry:
            return None
        data, expiry = entry
        if datetime.utcnow() > expiry:
            del self._store[draft_id]
            return None
        return data

    def delete(self, draft_id: str):
        if draft_id in self._store:
            del self._store[draft_id]

    def _cleanup(self):
        now = datetime.utcnow()
        expired = [k for k, (_, exp) in self._store.items() if now > exp]
        for k in expired:
            del self._store[k]

draft_cache = DraftCache()
