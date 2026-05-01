"""Pydantic contracts for inter-agent messages.

Every value that crosses an agent boundary is one of the models defined
here. No agent receives or returns a raw ``dict``. Keeping the
inter-agent vocabulary small and typed is what allows specialised
agents to be swapped, tested in isolation, and replayed deterministically.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# --- Vision Analyzer outputs ----------------------------------------------


class Shot(BaseModel):
    """One detected shot inside an asset's timeline."""

    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)
    description: str
    dominant_colors: list[str] = Field(default_factory=list)
    motion_intensity: float = Field(ge=0, le=1, default=0)


class TranscriptSegment(BaseModel):
    """One transcribed audio segment."""

    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)
    text: str
    language: str = "he"


class AssetFacts(BaseModel):
    """What the Vision Analyzer emits for a single uploaded asset."""

    asset_id: UUID
    duration_seconds: float = Field(ge=0)
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)
    has_audio: bool = False
    shots: list[Shot] = Field(default_factory=list)
    transcript: list[TranscriptSegment] = Field(default_factory=list)
    summary: str = ""


# --- Creative Director outputs --------------------------------------------


class BriefPlan(BaseModel):
    """The Creative Director's approved plan, handed to the Planner."""

    title: str
    intent: str = Field(
        description="One paragraph in Hebrew describing the edited video"
    )
    target_duration_seconds: float = Field(gt=0)
    style_notes: list[str] = Field(default_factory=list)
    music_direction: str | None = None
    pacing: Literal["slow", "medium", "fast"] = "medium"


# --- Editing Planner / pipeline EDL ---------------------------------------


class ClipReference(BaseModel):
    """A piece of an asset to be placed on the timeline."""

    asset_id: UUID
    source_start_seconds: float = Field(ge=0)
    source_end_seconds: float = Field(gt=0)


class TimelineClip(BaseModel):
    """One clip placed on a track at a specific timeline position."""

    clip: ClipReference
    timeline_start_seconds: float = Field(ge=0)
    transition_in: Literal["cut", "fade", "dissolve"] = "cut"
    transition_out: Literal["cut", "fade", "dissolve"] = "cut"


class Track(BaseModel):
    """A single video / audio track on the timeline."""

    kind: Literal["video", "audio"] = "video"
    clips: list[TimelineClip]


class AudioPlan(BaseModel):
    """High-level audio direction for the render pipeline."""

    music_url: str | None = None
    voice_over_asset_id: UUID | None = None
    duck_music_under_voice: bool = True
    target_lufs: float = -14.0


class SubtitlePlan(BaseModel):
    """Hebrew (or other) subtitles to burn onto the output."""

    language: str = "he"
    style: Literal["clean", "kinetic", "minimal"] = "clean"


class ColorPlan(BaseModel):
    """Color grade direction."""

    look: Literal["natural", "warm", "cool", "cinematic", "vibrant"] = "natural"
    contrast: float = Field(ge=-1, le=1, default=0)
    saturation: float = Field(ge=-1, le=1, default=0)


class OutputSpec(BaseModel):
    """Final encoder / container settings."""

    width: int = 1920
    height: int = 1080
    fps: int = 30
    container: Literal["mp4", "mov"] = "mp4"


class EditDecisionList(BaseModel):
    """The full, executable plan handed to the render pipeline.

    Versioned: ``version`` increments each time the planner or a
    specialist agent produces a new revision.
    """

    model_config = ConfigDict(populate_by_name=True)

    version: int = Field(ge=1)
    timeline: list[Track]
    audio: AudioPlan = Field(default_factory=AudioPlan)
    subtitles: SubtitlePlan | None = None
    color: ColorPlan | None = None
    output: OutputSpec = Field(default_factory=OutputSpec)

    @property
    def total_duration(self) -> timedelta:
        """Duration of the longest track on the timeline."""
        if not self.timeline:
            return timedelta(0)
        track_lengths = [
            max(
                (c.timeline_start_seconds for c in track.clips),
                default=0.0,
            )
            for track in self.timeline
        ]
        return timedelta(seconds=max(track_lengths))


# --- QA Reviewer outputs --------------------------------------------------


class QAFinding(BaseModel):
    """A single issue flagged by the QA reviewer."""

    severity: Literal["info", "warning", "error"]
    message: str
    suggestion: str | None = None


class QAReport(BaseModel):
    """The QA reviewer's verdict on an EDL or rendered output."""

    approved: bool
    findings: list[QAFinding] = Field(default_factory=list)
    summary: str = ""


# --- Generic envelope -----------------------------------------------------

AgentMessageContent = Annotated[
    AssetFacts | BriefPlan | EditDecisionList | QAReport,
    Field(discriminator=None),
]
