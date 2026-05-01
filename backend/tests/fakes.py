"""Lightweight in-memory fakes used by the unit-test suite.

Lets routes and services exercise the same code paths without booting
docker-compose. End-to-end coverage against real Postgres and MinIO
lives under ``tests/integration/``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
from typing import Any, BinaryIO
from uuid import UUID, uuid4

from app.agents.client import LLMClient, LLMMessage, LLMResponse
from app.core.errors import AssetNotFoundError, ExternalServiceError, NotFoundError
from app.db.enums import AssetStatus, JobStatus, MessageRole, SessionStatus
from app.storage.base import ObjectStore, StoredObject


class FakeProject:
    def __init__(self, *, name: str, description: str | None) -> None:
        now = datetime.now(UTC)
        self.id: UUID = uuid4()
        self.name = name
        self.description = description
        self.created_at = now
        self.updated_at = now


class FakeAsset:
    def __init__(
        self,
        *,
        project_id: UUID,
        filename: str,
        content_type: str | None,
        size_bytes: int | None,
        s3_bucket: str,
        s3_key: str,
        status: AssetStatus,
    ) -> None:
        now = datetime.now(UTC)
        self.id: UUID = uuid4()
        self.project_id = project_id
        self.filename = filename
        self.content_type = content_type
        self.size_bytes = size_bytes
        self.s3_bucket = s3_bucket
        self.s3_key = s3_key
        self.status = status
        self.analysis: dict[str, Any] | None = None
        self.created_at = now
        self.updated_at = now


class FakeProjectRepository:
    def __init__(self) -> None:
        self._rows: dict[UUID, FakeProject] = {}

    async def create(self, *, name: str, description: str | None) -> FakeProject:
        project = FakeProject(name=name, description=description)
        self._rows[project.id] = project
        return project

    async def get(self, project_id: UUID) -> FakeProject:
        project = self._rows.get(project_id)
        if project is None:
            raise NotFoundError(f"project {project_id} not found")
        return project

    async def list_all(self) -> list[FakeProject]:
        return sorted(self._rows.values(), key=lambda p: p.created_at, reverse=True)


class FakeAssetRepository:
    def __init__(self) -> None:
        self._rows: dict[UUID, FakeAsset] = {}

    async def create(
        self,
        *,
        project_id: UUID,
        filename: str,
        content_type: str | None,
        size_bytes: int | None,
        s3_bucket: str,
        s3_key: str,
        status: AssetStatus = AssetStatus.UPLOADED,
        analysis: dict[str, Any] | None = None,
    ) -> FakeAsset:
        asset = FakeAsset(
            project_id=project_id,
            filename=filename,
            content_type=content_type,
            size_bytes=size_bytes,
            s3_bucket=s3_bucket,
            s3_key=s3_key,
            status=status,
        )
        asset.analysis = analysis
        self._rows[asset.id] = asset
        return asset

    async def get(self, asset_id: UUID) -> FakeAsset:
        asset = self._rows.get(asset_id)
        if asset is None:
            raise AssetNotFoundError(f"asset {asset_id} not found")
        return asset

    async def list_for_project(self, project_id: UUID) -> list[FakeAsset]:
        return sorted(
            (a for a in self._rows.values() if a.project_id == project_id),
            key=lambda a: a.created_at,
            reverse=True,
        )


class InMemoryObjectStore(ObjectStore):
    """An ``ObjectStore`` that keeps bytes in a dict.

    Sufficient for unit tests that exercise the upload pipeline end to
    end without booting MinIO.
    """

    def __init__(self) -> None:
        self._objects: dict[tuple[str, str], bytes] = {}
        self._content_types: dict[tuple[str, str], str | None] = {}

    async def put(
        self,
        bucket: str,
        key: str,
        data: BinaryIO,
        *,
        content_type: str | None = None,
    ) -> StoredObject:
        body = data.read()
        self._objects[(bucket, key)] = body
        self._content_types[(bucket, key)] = content_type
        return StoredObject(
            bucket=bucket, key=key, size_bytes=len(body), content_type=content_type
        )

    async def get(self, bucket: str, key: str) -> bytes:
        try:
            return self._objects[(bucket, key)]
        except KeyError as exc:
            raise ExternalServiceError(f"missing s3://{bucket}/{key}") from exc

    async def delete(self, bucket: str, key: str) -> None:
        self._objects.pop((bucket, key), None)
        self._content_types.pop((bucket, key), None)

    async def exists(self, bucket: str, key: str) -> bool:
        return (bucket, key) in self._objects

    async def presigned_get_url(self, bucket: str, key: str, *, ttl_seconds: int) -> str:
        if (bucket, key) not in self._objects:
            raise ExternalServiceError(f"missing s3://{bucket}/{key}")
        return f"http://fake-store.local/{bucket}/{key}?ttl={ttl_seconds}"

    async def health_check(self) -> None:
        return None


def make_upload_buffer(payload: bytes) -> BinaryIO:
    """Build a ``BinaryIO`` that mimics ``UploadFile.file`` for tests."""
    return BytesIO(payload)


# --- Sessions / messages --------------------------------------------------


class FakeSession:
    def __init__(self, *, project_id: UUID) -> None:
        now = datetime.now(UTC)
        self.id: UUID = uuid4()
        self.project_id = project_id
        self.status: SessionStatus = SessionStatus.ACTIVE
        self.created_at = now
        self.updated_at = now
        self.messages: list["FakeMessage"] = []


class FakeMessage:
    def __init__(
        self,
        *,
        session_id: UUID,
        role: MessageRole,
        content: str,
        agent_name: str | None = None,
    ) -> None:
        now = datetime.now(UTC)
        self.id: UUID = uuid4()
        self.session_id = session_id
        self.role = role
        self.content = content
        self.agent_name = agent_name
        self.created_at = now
        self.updated_at = now


class FakeSessionRepository:
    def __init__(self) -> None:
        self._rows: dict[UUID, FakeSession] = {}

    async def create(self, *, project_id: UUID) -> FakeSession:
        chat = FakeSession(project_id=project_id)
        self._rows[chat.id] = chat
        return chat

    async def get(self, session_id: UUID) -> FakeSession:
        chat = self._rows.get(session_id)
        if chat is None:
            raise NotFoundError(f"session {session_id} not found")
        return chat

    async def get_with_messages(self, session_id: UUID) -> FakeSession:
        return await self.get(session_id)

    async def list_for_project(self, project_id: UUID) -> list[FakeSession]:
        return sorted(
            (s for s in self._rows.values() if s.project_id == project_id),
            key=lambda s: s.created_at,
            reverse=True,
        )

    async def close(self, session_id: UUID) -> FakeSession:
        chat = await self.get(session_id)
        chat.status = SessionStatus.CLOSED
        return chat


class FakeMessageRepository:
    def __init__(self, sessions: FakeSessionRepository) -> None:
        self._sessions = sessions

    async def append(
        self,
        *,
        session_id: UUID,
        role: MessageRole,
        content: str,
        agent_name: str | None = None,
    ) -> FakeMessage:
        chat = await self._sessions.get(session_id)
        message = FakeMessage(
            session_id=session_id, role=role, content=content, agent_name=agent_name
        )
        chat.messages.append(message)
        return message

    async def list_for_session(self, session_id: UUID) -> list[FakeMessage]:
        chat = await self._sessions.get(session_id)
        return list(chat.messages)


# --- EDL versions / render jobs ------------------------------------------


class FakeEdlVersion:
    def __init__(
        self,
        *,
        project_id: UUID,
        version_number: int,
        edl: dict[str, Any],
        session_id: UUID | None = None,
    ) -> None:
        now = datetime.now(UTC)
        self.id: UUID = uuid4()
        self.project_id = project_id
        self.version_number = version_number
        self.edl = edl
        self.session_id = session_id
        self.created_at = now
        self.updated_at = now


class FakeEdlVersionRepository:
    def __init__(self) -> None:
        self._rows: dict[UUID, FakeEdlVersion] = {}

    async def insert(
        self,
        *,
        project_id: UUID,
        edl: dict[str, Any],
        session_id: UUID | None = None,
    ) -> FakeEdlVersion:
        existing = [r for r in self._rows.values() if r.project_id == project_id]
        next_version = max((r.version_number for r in existing), default=0) + 1
        row = FakeEdlVersion(
            project_id=project_id,
            version_number=next_version,
            edl=edl,
            session_id=session_id,
        )
        self._rows[row.id] = row
        return row

    async def get(self, edl_version_id: UUID) -> FakeEdlVersion:
        row = self._rows.get(edl_version_id)
        if row is None:
            raise NotFoundError(f"edl_version {edl_version_id} not found")
        return row

    async def latest_for_project(self, project_id: UUID) -> FakeEdlVersion | None:
        rows = [r for r in self._rows.values() if r.project_id == project_id]
        if not rows:
            return None
        return max(rows, key=lambda r: r.version_number)


class FakeRenderJob:
    def __init__(
        self, *, project_id: UUID, edl_version_id: UUID
    ) -> None:
        now = datetime.now(UTC)
        self.id: UUID = uuid4()
        self.project_id = project_id
        self.edl_version_id = edl_version_id
        self.status: JobStatus = JobStatus.PENDING
        self.output_bucket: str | None = None
        self.output_key: str | None = None
        self.error_message: str | None = None
        self.created_at = now
        self.updated_at = now


class FakeRenderJobRepository:
    def __init__(self) -> None:
        self._rows: dict[UUID, FakeRenderJob] = {}

    async def create(
        self, *, project_id: UUID, edl_version_id: UUID
    ) -> FakeRenderJob:
        job = FakeRenderJob(project_id=project_id, edl_version_id=edl_version_id)
        self._rows[job.id] = job
        return job

    async def get(self, job_id: UUID) -> FakeRenderJob:
        job = self._rows.get(job_id)
        if job is None:
            raise NotFoundError(f"render_job {job_id} not found")
        return job

    async def mark_running(self, job_id: UUID) -> FakeRenderJob:
        job = await self.get(job_id)
        job.status = JobStatus.RUNNING
        return job

    async def mark_succeeded(
        self, job_id: UUID, *, output_bucket: str, output_key: str
    ) -> FakeRenderJob:
        job = await self.get(job_id)
        job.status = JobStatus.SUCCEEDED
        job.output_bucket = output_bucket
        job.output_key = output_key
        job.error_message = None
        return job

    async def mark_failed(
        self, job_id: UUID, *, error_message: str
    ) -> FakeRenderJob:
        job = await self.get(job_id)
        job.status = JobStatus.FAILED
        job.error_message = error_message
        return job

    async def list_for_project(self, project_id: UUID) -> list[FakeRenderJob]:
        return sorted(
            (j for j in self._rows.values() if j.project_id == project_id),
            key=lambda j: j.created_at,
            reverse=True,
        )


# --- LLM ------------------------------------------------------------------


class ScriptedLLM(LLMClient):
    """Returns canned replies in order; records every call."""

    def __init__(self, replies: list[str]) -> None:
        self.replies = list(replies)
        self.calls: list[dict[str, object]] = []

    async def complete(
        self,
        *,
        model: str,
        system_prompt: str,
        messages: list[LLMMessage],
        max_tokens: int = 16000,
        cache_system_prompt: bool = True,
    ) -> LLMResponse:
        self.calls.append(
            {
                "model": model,
                "system_prompt": system_prompt,
                "messages": list(messages),
            }
        )
        return LLMResponse(text=self.replies.pop(0))
