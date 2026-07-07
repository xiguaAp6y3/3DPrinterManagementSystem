from dataclasses import dataclass
from hashlib import sha256

from sqlalchemy.orm import Session


@dataclass(frozen=True)
class IdempotencyResult:
    exists: bool
    response_body: str | None = None
    status_code: int | None = None
    resource_type: str | None = None
    resource_id: int | None = None


def request_hash(raw_body: bytes) -> str:
    return sha256(raw_body).hexdigest()


class IdempotencyService:
    def __init__(self, db: Session):
        self.db = db

    def check(self, scope: str, key: str, body_hash: str) -> IdempotencyResult:
        # TODO: query idempotency_keys and verify request_hash.
        return IdempotencyResult(exists=False)

    def save_result(
        self,
        scope: str,
        key: str,
        body_hash: str,
        response_body: str,
        status_code: int,
        resource_type: str | None = None,
        resource_id: int | None = None,
    ) -> None:
        # TODO: insert idempotency_keys in same transaction as business operation.
        return None
