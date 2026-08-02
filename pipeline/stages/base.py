from __future__ import annotations

from abc import ABC, abstractmethod

from pipeline.context import PipelineContext


class Stage(ABC):
    name: str = "stage"
    requires: tuple[str, ...] = ()
    produces: tuple[str, ...] = ()

    @abstractmethod
    def run(self, ctx: PipelineContext) -> None:
        """Mutate ctx in place: read ctx.data[...], write results back."""

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r}>"