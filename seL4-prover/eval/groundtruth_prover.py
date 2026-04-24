from pathlib import Path
from typing import List

from pydantic import BaseModel, TypeAdapter

from data.FVELv2Data import FVELv2Data
from data.lemma import Lemma, LemmaProtocol
from provers.lib import ProverProtocol


class GroundTruthProverConfig(BaseModel):
    dataset_path: Path


class GroundTruthProver(ProverProtocol[GroundTruthProverConfig]):
    def __init__(self, dataset_path: Path) -> None:
        config = GroundTruthProverConfig(dataset_path=dataset_path)
        self.load_config(config)

    def load_config(self, config: GroundTruthProverConfig) -> None:
        self.config = config
        self.data: FVELv2Data = TypeAdapter(FVELv2Data).validate_json(
            self.config.dataset_path.read_text()
        )

    def prove(self, lemma: LemmaProtocol, port: int) -> List[str]:
        # Just return the ground truth proof
        found: Lemma | None = next(
            (
                item
                for split in self.data
                for item in self.data[split]
                if (item.statement, item.theory, item.session)
                == (lemma.statement, lemma.theory, lemma.session)
            ),
            None,
        )

        return [s.step for s in found.proof] if found is not None else []
