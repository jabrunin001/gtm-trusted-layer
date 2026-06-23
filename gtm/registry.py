from pathlib import Path
from typing import Literal
import yaml
from pydantic import BaseModel
from gtm.config import REGISTRY_PATH


class MetricDef(BaseModel):
    name: str
    description: str
    grain: str
    source_of_truth: str
    owning_org: Literal["gtm_ops", "finance"]
    abs_tolerance: float = 0.0
    rel_tolerance: float = 0.0
    freshness_sources: list[str] = []


class Registry(BaseModel):
    metrics: list[MetricDef]

    def names(self) -> set[str]:
        return {m.name for m in self.metrics}

    def get(self, name: str) -> MetricDef:
        for m in self.metrics:
            if m.name == name:
                return m
        raise KeyError(name)


def load_registry(path: Path = REGISTRY_PATH) -> Registry:
    data = yaml.safe_load(Path(path).read_text())
    return Registry.model_validate(data)
