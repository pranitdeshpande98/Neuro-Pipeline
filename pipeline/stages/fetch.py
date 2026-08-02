from __future__ import annotations

import logging
from pathlib import Path

from pipeline.context import PipelineContext
from pipeline.stages.base import Stage
from pipeline.storage import ObjectStore

logger = logging.getLogger(__name__)


class FetchInputsStage(Stage):
    name = "fetch_inputs"
    produces = ("input_paths",)

    def __init__(self, store: ObjectStore):
        self._store = store

    def run(self, ctx: PipelineContext) -> None:
        raw_dir = ctx.workdir / "raw"
        paths: list[Path] = []
        for ref in ctx.inputs:
            dest = raw_dir / Path(ref.key).name
            logger.info("downloading %s", ref.key)
            self._store.download(ref.key, dest)
            paths.append(dest)

        ctx.data["input_paths"] = paths
        ctx.metrics["n_inputs"] = len(paths)