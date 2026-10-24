from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Clip(Strict):
    asset_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    start: float = Field(ge=0, le=300)
    end: float = Field(gt=0, le=300)
    zoom: float = Field(default=1.0, ge=1, le=1.3)
    volume: float = Field(default=1.0, ge=0, le=2)
    reason: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def range_valid(self):
        if self.end - self.start < 0.12:
            raise ValueError("Clips must be at least 0.12 seconds")
        return self


class MotionGraphic(Strict):
    template: Literal["kinetic_title", "callout", "lower_third", "framecraft"]
    text: str = Field(min_length=1, max_length=100)
    detail: str = Field(default="", max_length=140)
    start: float = Field(ge=0, le=180)
    duration: float = Field(ge=0.3, le=10)
    position: Literal["center", "left", "right", "lower_left"] = "center"
    palette: Literal["cream", "dark"] = "cream"

    @model_validator(mode="after")
    def template_range(self):
        if self.template == "framecraft" and self.duration < 3:
            raise ValueError("Framecraft needs at least 3 seconds for its reveal and closing hold")
        return self


class Timeline(Strict):
    clips: list[Clip] = Field(default_factory=list, max_length=60)
    grade: Literal["none", "subtle", "neutral_punch", "warm_cinematic", "auto"] = "none"
    aspect: Literal["landscape", "portrait"] = "landscape"
    captions: Literal["none", "static", "pop"] = "none"
    title: str = Field(default="", max_length=100)
    fade_out: bool = False
    music_asset_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")
    music_volume: float = Field(default=0.12, ge=0, le=0.5)
    motion_graphics: list[MotionGraphic] = Field(default_factory=list, max_length=12)

    @model_validator(mode="after")
    def full_frame_scene(self):
        if any(g.template == "framecraft" for g in self.motion_graphics) and len(self.motion_graphics) != 1:
            raise ValueError("Use one Framecraft scene per edit; it is a full-frame illustration")
        return self


class EditPlan(Strict):
    summary: str = Field(max_length=3000)
    warnings: list[str] = Field(max_length=20)
    timeline: Timeline


class ProjectCreate(Strict):
    name: str = Field(default="Untitled project", min_length=1, max_length=100)


class TimelineSave(Strict):
    revision: int = Field(ge=0)
    timeline: Timeline


class JobCreate(Strict):
    kind: Literal["generate", "plan", "preview", "export", "reference"]
    prompt: str = Field(default="", max_length=6000)
    style_id: str | None = Field(default=None, max_length=100)
    reference_asset_ids: list[str] = Field(default_factory=list, max_length=8)
    aspect: Literal["landscape", "portrait"] = "portrait"
    input_asset_ids: list[str] = Field(default_factory=list, max_length=60)


class TranscriptCreate(Strict):
    text: str = Field(min_length=1, max_length=20000)
    name: str = Field(default="Transcript.txt", min_length=1, max_length=100)


class MarkdownSave(Strict):
    markdown: str = Field(min_length=1, max_length=50000)


class URLImport(Strict):
    url: str = Field(max_length=2048)


def strict_json_schema(model: type[BaseModel]) -> dict:
    schema = model.model_json_schema()
    def walk(v):
        if isinstance(v, dict):
            v.pop("default", None)
            if v.get("type") == "object":
                v["additionalProperties"] = False
                v["required"] = list(v.get("properties", {}))
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)
    walk(schema)
    return schema
