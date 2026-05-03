"""Unit tests for :class:`app.services.analysis.AssetAnalysisService`."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.core.errors import ExternalServiceError
from app.db.enums import AssetStatus
from app.pipeline.probe import Probe, ProbeResult, StubProbe
from app.services.analysis import AssetAnalysisService
from tests.fakes import (
    FakeAssetRepository,
    FakeProjectRepository,
    InMemoryObjectStore,
    make_upload_buffer,
)


class _FailingProbe(Probe):
    async def probe(self, path: Path) -> ProbeResult:
        raise ExternalServiceError("ffprobe blew up")


@pytest.fixture
def settings() -> Settings:
    return Settings(environment="test")


async def _seed_asset(
    *,
    settings: Settings,
    projects: FakeProjectRepository,
    assets: FakeAssetRepository,
    store: InMemoryObjectStore,
):
    project = await projects.create(name="p", description=None)
    asset = await assets.create(
        project_id=project.id,
        filename="clip.mp4",
        content_type="video/mp4",
        size_bytes=4,
        s3_bucket=settings.s3_bucket_assets,
        s3_key=f"{project.id}/{uuid4()}/clip.mp4",
        status=AssetStatus.UPLOADED,
    )
    await store.put(
        asset.s3_bucket,
        asset.s3_key,
        make_upload_buffer(b"\x00\x01\x02\x03"),
        content_type="video/mp4",
    )
    return project, asset


async def test_analyze_writes_probe_facts_and_marks_ready(
    settings: Settings,
) -> None:
    projects = FakeProjectRepository()
    assets = FakeAssetRepository()
    store = InMemoryObjectStore()
    _, asset = await _seed_asset(settings=settings, projects=projects, assets=assets, store=store)
    service = AssetAnalysisService(
        probe=StubProbe(duration_seconds=12.5, width=1920, height=1080, has_audio=True),
        object_store=store,
        assets=assets,
    )

    updated = await service.analyze(asset.id)

    assert updated.status is AssetStatus.READY
    assert updated.analysis is not None
    assert updated.analysis["duration_seconds"] == 12.5
    assert updated.analysis["width"] == 1920
    assert updated.analysis["height"] == 1080
    assert updated.analysis["has_audio"] is True


async def test_analyze_marks_failed_and_stores_error_when_probe_raises(
    settings: Settings,
) -> None:
    projects = FakeProjectRepository()
    assets = FakeAssetRepository()
    store = InMemoryObjectStore()
    _, asset = await _seed_asset(settings=settings, projects=projects, assets=assets, store=store)
    service = AssetAnalysisService(probe=_FailingProbe(), object_store=store, assets=assets)

    updated = await service.analyze(asset.id)

    assert updated.status is AssetStatus.FAILED
    assert updated.analysis is not None
    assert "ffprobe blew up" in updated.analysis["error"]


async def test_analyze_preserves_prior_analysis_keys(settings: Settings) -> None:
    projects = FakeProjectRepository()
    assets = FakeAssetRepository()
    store = InMemoryObjectStore()
    _, asset = await _seed_asset(settings=settings, projects=projects, assets=assets, store=store)
    asset.analysis = {"summary": "warm wedding ceremony", "shots": ["s1", "s2"]}

    service = AssetAnalysisService(
        probe=StubProbe(duration_seconds=30.0),
        object_store=store,
        assets=assets,
    )

    updated = await service.analyze(asset.id)

    assert updated.analysis is not None
    # Probe fields populated.
    assert updated.analysis["duration_seconds"] == 30.0
    # Prior keys retained.
    assert updated.analysis["summary"] == "warm wedding ceremony"
    assert updated.analysis["shots"] == ["s1", "s2"]


async def test_analyze_raises_when_asset_does_not_exist(
    settings: Settings,
) -> None:
    service = AssetAnalysisService(
        probe=StubProbe(),
        object_store=InMemoryObjectStore(),
        assets=FakeAssetRepository(),
    )

    from app.core.errors import AssetNotFoundError

    with pytest.raises(AssetNotFoundError):
        await service.analyze(uuid4())


# --- vision pass ---------------------------------------------------------


async def test_analyze_runs_vision_pass_when_extractor_and_llm_provided(
    settings: Settings,
) -> None:
    from app.agents.client import LLMMessage, LLMResponse
    from app.pipeline.frame_extractor import StubFrameExtractor

    projects = FakeProjectRepository()
    assets = FakeAssetRepository()
    store = InMemoryObjectStore()
    _, asset = await _seed_asset(settings=settings, projects=projects, assets=assets, store=store)

    captured: dict[str, object] = {}

    class _RecordingLLM:
        async def complete(
            self,
            *,
            model: str,
            system_prompt: str,
            messages: list[LLMMessage],
            max_tokens: int = 16000,
            cache_system_prompt: bool = True,
        ) -> LLMResponse:
            captured["messages"] = messages
            captured["model"] = model
            return LLMResponse(
                text=(
                    '{"summary":"סיכום קצר",'
                    '"shots":[{"start_seconds":0,"end_seconds":12,'
                    '"description":"כל הסרטון","dominant_colors":[],'
                    '"motion_intensity":0.3}]}'
                ),
            )

    service = AssetAnalysisService(
        probe=StubProbe(duration_seconds=12.0),
        object_store=store,
        assets=assets,
        frame_extractor=StubFrameExtractor(),
        llm=_RecordingLLM(),  # type: ignore[arg-type]
    )

    updated = await service.analyze(asset.id)

    assert updated.status is AssetStatus.READY
    assert updated.analysis is not None
    assert updated.analysis["summary"] == "סיכום קצר"
    shots = updated.analysis["shots"]
    assert isinstance(shots, list) and len(shots) == 1
    # Probe facts still present (vision merges on top, doesn't replace).
    assert updated.analysis["duration_seconds"] == 12.0
    # The LLM saw image blocks attached to the user message.
    sent = captured["messages"]
    assert isinstance(sent, list) and len(sent) == 1
    assert len(sent[0].images) > 0


async def test_vision_pass_skipped_silently_when_extractor_missing(
    settings: Settings,
) -> None:
    """No frame extractor + no LLM = probe-only, no vision pass."""
    projects = FakeProjectRepository()
    assets = FakeAssetRepository()
    store = InMemoryObjectStore()
    _, asset = await _seed_asset(settings=settings, projects=projects, assets=assets, store=store)

    service = AssetAnalysisService(
        probe=StubProbe(duration_seconds=10.0),
        object_store=store,
        assets=assets,
        # Both omitted => vision pass is skipped.
    )
    updated = await service.analyze(asset.id)

    assert updated.status is AssetStatus.READY
    assert updated.analysis is not None
    assert "summary" not in updated.analysis
    assert "shots" not in updated.analysis


async def test_vision_pass_failure_does_not_break_probe_facts(
    settings: Settings,
) -> None:
    """Vision step that raises is logged, but the asset still becomes ready."""
    from app.agents.client import LLMMessage, LLMResponse
    from app.core.errors import ExternalServiceError
    from app.pipeline.frame_extractor import StubFrameExtractor

    projects = FakeProjectRepository()
    assets = FakeAssetRepository()
    store = InMemoryObjectStore()
    _, asset = await _seed_asset(settings=settings, projects=projects, assets=assets, store=store)

    class _AngryLLM:
        async def complete(
            self,
            *,
            model: str,
            system_prompt: str,
            messages: list[LLMMessage],
            max_tokens: int = 16000,
            cache_system_prompt: bool = True,
        ) -> LLMResponse:
            raise ExternalServiceError("anthropic 500")

    service = AssetAnalysisService(
        probe=StubProbe(duration_seconds=10.0),
        object_store=store,
        assets=assets,
        frame_extractor=StubFrameExtractor(),
        llm=_AngryLLM(),  # type: ignore[arg-type]
    )
    updated = await service.analyze(asset.id)

    # Probe stage succeeded — asset is ready, vision keys absent.
    assert updated.status is AssetStatus.READY
    assert updated.analysis is not None
    assert updated.analysis["duration_seconds"] == 10.0
    assert "summary" not in updated.analysis


# --- transcript pass ------------------------------------------------------


async def test_analyze_runs_transcriber_when_audio_present(
    settings: Settings,
) -> None:
    from app.agents.contracts import TranscriptSegment
    from app.pipeline.transcriber import StubTranscriber

    projects = FakeProjectRepository()
    assets = FakeAssetRepository()
    store = InMemoryObjectStore()
    _, asset = await _seed_asset(settings=settings, projects=projects, assets=assets, store=store)

    canned = [
        TranscriptSegment(start_seconds=0, end_seconds=2.5, text="שלום", language="he"),
        TranscriptSegment(start_seconds=2.5, end_seconds=5, text="עולם", language="he"),
    ]

    service = AssetAnalysisService(
        probe=StubProbe(duration_seconds=5.0, has_audio=True),
        object_store=store,
        assets=assets,
        transcriber=StubTranscriber(segments=canned),
    )

    updated = await service.analyze(asset.id)

    assert updated.status is AssetStatus.READY
    assert updated.analysis is not None
    transcript = updated.analysis["transcript"]
    assert isinstance(transcript, list) and len(transcript) == 2
    assert transcript[0]["text"] == "שלום"
    # Probe facts still present.
    assert updated.analysis["duration_seconds"] == 5.0


async def test_transcribe_skipped_when_no_audio(settings: Settings) -> None:
    from app.pipeline.transcriber import StubTranscriber

    projects = FakeProjectRepository()
    assets = FakeAssetRepository()
    store = InMemoryObjectStore()
    _, asset = await _seed_asset(settings=settings, projects=projects, assets=assets, store=store)

    service = AssetAnalysisService(
        probe=StubProbe(duration_seconds=10.0, has_audio=False),
        object_store=store,
        assets=assets,
        transcriber=StubTranscriber(
            segments=[]
        ),  # would return [] anyway, but the call should not happen
    )
    updated = await service.analyze(asset.id)

    assert updated.status is AssetStatus.READY
    assert updated.analysis is not None
    assert "transcript" not in updated.analysis


async def test_transcribe_failure_does_not_break_probe_facts(
    settings: Settings,
) -> None:

    from app.agents.contracts import TranscriptSegment
    from app.pipeline.transcriber import Transcriber

    class _AngryTranscriber(Transcriber):
        async def transcribe(
            self, path: Path, *, language: str | None = None
        ) -> list[TranscriptSegment]:
            raise ExternalServiceError("whisper crashed")

    projects = FakeProjectRepository()
    assets = FakeAssetRepository()
    store = InMemoryObjectStore()
    _, asset = await _seed_asset(settings=settings, projects=projects, assets=assets, store=store)

    service = AssetAnalysisService(
        probe=StubProbe(duration_seconds=10.0, has_audio=True),
        object_store=store,
        assets=assets,
        transcriber=_AngryTranscriber(),
    )
    updated = await service.analyze(asset.id)

    assert updated.status is AssetStatus.READY
    assert updated.analysis is not None
    assert updated.analysis["duration_seconds"] == 10.0
    assert "transcript" not in updated.analysis
