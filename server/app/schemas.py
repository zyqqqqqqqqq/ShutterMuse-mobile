from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class BBox(BaseModel):
    x1: float = Field(ge=0.0, le=1.0)
    y1: float = Field(ge=0.0, le=1.0)
    x2: float = Field(ge=0.0, le=1.0)
    y2: float = Field(ge=0.0, le=1.0)


Decision = Literal["keep", "refine", "reject"]


class CompositionResponse(BaseModel):
    decision: Decision
    bbox: Optional[BBox] = None
    message: Optional[str] = None
    latency_ms: int


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    backend: Optional[str] = None
    detail: Optional[str] = None


class Keypoint(BaseModel):
    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)
    visible: bool = True


class PoseResponse(BaseModel):
    keypoints: List[Optional[Keypoint]]
    message: str
    parse_ok: bool
    latency_ms: int


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody
