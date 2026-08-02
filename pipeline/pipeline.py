from __future__ import annotations

import logging
import time
from collections.abc import Sequence

from pipeline.context import PipelineContext
from pipeline.stages.base import Stage

logger = logging.getLogger(__name__)


class PipelineDefinitionError(RuntimeError):
    """The stage list is internally inconsistent."""


class StageFailure(RuntimeError):
    """A stage raised during execution."""

    def __init__(self, stage_name: str, original: Exception):
        super().__init__(f"stage '{stage_name}' failed: {original}")
        self.stage_name = stage_name
        self.original = original


class Pipeline:
    def __init__(self, stages: Sequence[Stage]):
        self.stages = list(stages)
        self._validate()

    def _validate(self) -> None:
        """Fail before doing any work if the ordering can't satisfy dependencies."""
        available: set[str] = set()
        for stage in self.stages:
            missing = [key for key in stage.requires if key not in available]
            if missing:
                raise PipelineDefinitionError(
                    f"stage '{stage.name}' requires {missing}, not produced by any "
                    f"earlier stage (available: {sorted(available)})"
                )
            available.update(stage.produces)

    def run(self, ctx: PipelineContext) -> PipelineContext:
        timings: dict[str, float] = {}
        for stage in self.stages:
            logger.info("stage start: %s", stage.name)
            started = time.perf_counter()
            try:
                stage.run(ctx)
            except Exception as exc:
                logger.exception("stage failed: %s", stage.name)
                raise StageFailure(stage.name, exc) from exc

            unset = [key for key in stage.produces if key not in ctx.data]
            if unset:
                raise PipelineDefinitionError(
                    f"stage '{stage.name}' declares it produces {unset} but did not set them"
                )

            elapsed = time.perf_counter() - started
            timings[stage.name] = round(elapsed, 3)
            logger.info("stage done: %s (%.2fs)", stage.name, elapsed)

        ctx.metrics["stage_seconds"] = timings
        return ctx