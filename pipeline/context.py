from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class InputRef:
    key: str
    external_id: str


@dataclass
class ArtifactRef:
    kind: str
    path: Path
    key: str | None = None
    content_type: str = "application/octet-stream"


@dataclass
class PipelineContext:
    run_id: int
    subject: str
    dataset: str
    pipeline_version: str
    params: dict[str, Any]
    inputs: list[InputRef]
    workdir: Path

    data: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    artifacts: list[ArtifactRef] = field(default_factory=list)

    @classmethod
    def from_manifest(cls, manifest: dict, workdir: Path) -> "PipelineContext":
        return cls(
            run_id=manifest["run_id"],
            subject=manifest["subject"],
            dataset=manifest["dataset"],
            pipeline_version=manifest.get("pipeline_version", "unknown"),
            params=manifest.get("params", {}),
            inputs=[InputRef(**item) for item in manifest["inputs"]],
            workdir=workdir,
        )

    def add_artifact(
        self,
        kind: str,
        path: Path | str,
        content_type: str = "application/octet-stream",
    ) -> None:
        self.artifacts.append(
            ArtifactRef(kind=kind, path=Path(path), content_type=content_type)
        )