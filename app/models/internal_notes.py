from dataclasses import dataclass, field
from datetime import datetime

from app.domain.clock import now


@dataclass
class NotaInterna:
    id: int | None = field(default=None, kw_only=True)
    ticket_id: int
    author_id: int
    body: str
    created_at: datetime = field(default_factory=now)
