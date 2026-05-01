"""Asset analysis use case.

Pulls one asset's bytes onto local disk, runs a :class:`Probe` over it
(today: ``ffprobe`` for duration / resolution / audio presence; later:
also Whisper transcription and scene detection), and persists the
result into ``assets.analysis`` while flipping the asset's
``status``.

Lives in ``services`` rather than in ``pipeline`` because it is the
orchestration layer - it owns the DB and storage interactions. The
probe itself stays a pure function of ``Path → ProbeResult``.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from uuid import UUID

from app.core.errors import AppError
from app.core.logging import get_logger
from app.db.enums import AssetStatus
from app.db.models import Asset
from app.pipeline.probe import Probe, ProbeResult
from app.repositories.assets import AssetRepository
from app.storage.base import ObjectStore


class AssetAnalysisService:
    """Runs the deterministic analysis stage on a stored asset."""

    def __init__(
        self,
        *,
        probe: Probe,
        object_store: ObjectStore,
        assets: AssetRepository,
    ) -> None:
        self._probe = probe
        self._object_store = object_store
        self._assets = assets
        self._log = get_logger("services.analysis")

    async def analyze(self, asset_id: UUID) -> Asset:
        """Probe ``asset_id`` and persist the result.

        On probe failure the asset transitions to ``status = failed``;
        the bytes stay in object storage so a later re-analysis can
        try again. The method does not raise on probe failures - the
        outcome is fully reflected in the returned :class:`Asset`
        row.
        """
        asset = await self._assets.get(asset_id)
        asset.status = AssetStatus.ANALYZING

        scratch = Path(tempfile.mkdtemp(prefix="probe-"))
        try:
            local_path = scratch / Path(asset.filename).name
            data = await self._object_store.get(asset.s3_bucket, asset.s3_key)
            local_path.write_bytes(data)

            try:
                result = await self._probe.probe(local_path)
            except AppError as exc:
                self._log.warning(
                    "analysis.probe_failed",
                    asset_id=str(asset.id),
                    error=exc.message,
                )
                asset.status = AssetStatus.FAILED
                asset.analysis = {"error": exc.message}
                return asset

            asset.analysis = _merge_probe_into_analysis(asset.analysis, result)
            asset.status = AssetStatus.READY
            self._log.info(
                "analysis.complete",
                asset_id=str(asset.id),
                duration_seconds=result.duration_seconds,
            )
            return asset
        finally:
            shutil.rmtree(scratch, ignore_errors=True)


def _merge_probe_into_analysis(
    existing: dict | None, result: ProbeResult
) -> dict:
    """Layer probe facts on top of any prior analysis.

    Future stages (Whisper transcription, scene detection, Vision
    Analyzer summaries) will write to additional keys of the same
    ``analysis`` blob - e.g. ``transcript``, ``shots``, ``summary``.
    Keeping a merge step here means re-running the probe alone does
    not blow away those richer fields.
    """
    merged: dict[str, object] = dict(existing or {})
    merged.update(
        {
            "duration_seconds": result.duration_seconds,
            "width": result.width,
            "height": result.height,
            "has_audio": result.has_audio,
            "container_format": result.container_format,
        }
    )
    return merged
