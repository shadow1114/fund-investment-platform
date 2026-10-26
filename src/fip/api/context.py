from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request


@dataclass(frozen=True)
class Principal:
    user_id: str
    roles: tuple[str, ...]
    can_review_decisions: bool
    can_review_classifications: bool = False
    can_manage_data_ingestion: bool = False


def principal_from_request(request: Request) -> Principal:
    from fip.api.auth import authenticate_request

    return authenticate_request(request)
