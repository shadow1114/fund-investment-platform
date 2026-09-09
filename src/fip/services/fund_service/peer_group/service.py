from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.orm import Session

from fip.platform.decision_data.context import DecisionExecutionContext
from fip.services.fund_service.peer_group.builder import build_peer_groups
from fip.services.fund_service.peer_group.models import PeerGroupCandidate, PeerGroupDraft
from fip.services.fund_service.peer_group.repository import PeerGroupSnapshotRepository


class PeerGroupCandidateProvider(Protocol):
    def load(self, context: DecisionExecutionContext) -> Sequence[PeerGroupCandidate]: ...


@dataclass(frozen=True, slots=True)
class PersistedPeerGroup:
    snapshot_id: int
    draft: PeerGroupDraft


@dataclass(frozen=True, slots=True)
class PeerGroupStageResult:
    groups: tuple[PersistedPeerGroup, ...]


class PeerGroupStage:
    def __init__(
        self,
        session: Session,
        *,
        candidate_provider: PeerGroupCandidateProvider,
        supported_profiles: Mapping[str, str],
        policy_version_id: int,
    ) -> None:
        self._repository = PeerGroupSnapshotRepository(session)
        self._candidate_provider = candidate_provider
        self._supported_profiles = supported_profiles
        self._policy_version_id = policy_version_id

    def run(self, context: DecisionExecutionContext) -> PeerGroupStageResult:
        drafts = build_peer_groups(
            self._candidate_provider.load(context),
            self._supported_profiles,
        )
        return PeerGroupStageResult(
            tuple(
                PersistedPeerGroup(
                    self._repository.save(
                        decision_id=context.decision_id,
                        decision_at=context.decision_at,
                        policy_version_id=self._policy_version_id,
                        draft=draft,
                    ),
                    draft,
                )
                for draft in drafts
            )
        )