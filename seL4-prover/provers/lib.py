from logging import Logger
from typing import Any, List, Protocol, Tuple, TypeVar

from pydantic import BaseModel
from vllm.inputs import PromptType

from data.lemma import LemmaProtocol


class SamplingParamsModel(BaseModel):
    temperature: float = 1.0
    max_tokens: int = 2048
    top_p: float = 0.95
    n: int = 128
    logprobs: int = 1


class InferenceBatchRequest(BaseModel):
    items: List[PromptType | list[dict[str, Any]]]
    sampling_params: SamplingParamsModel = SamplingParamsModel()
    use_tqdm: bool = False


class InferenceBatchResponse(BaseModel):
    outputs: list[list[Tuple[str, float]]]


class LogprobSamplingParamsModel(BaseModel):
    temperature: float = 0.0
    max_tokens: int = 2048
    top_p: float = 1.0
    n: int = 1
    logprobs: int = 1
    prompt_logprobs: int = 1


class ComputeLogprobRequest(BaseModel):
    state: str
    possible_steps: List[str]
    limit: int
    sampling_params: LogprobSamplingParamsModel
    use_tqdm: bool = False


ProverCfgT = TypeVar("ProverCfgT", bound=BaseModel)


class ProverProtocol(Protocol[ProverCfgT]):
    config: ProverCfgT
    logger: Logger

    def load_config(self, config: ProverCfgT) -> None: ...

    def prove(self, lemma: LemmaProtocol, port: int) -> List[str]: ...
