from logging import Logger
from typing import Any, Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel, ConfigDict
from vllm.inputs import PromptType

from data.lemma import LemmaProtocol


class SamplingParamsModel(BaseModel):
    temperature: float = 1.0
    max_tokens: int = 2048
    top_p: float = 0.95
    n: int = 128
    logprobs: int = 1


class InferenceBatchRequest(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    items: list[PromptType | list[dict[str, Any]]]
    sampling_params: SamplingParamsModel = SamplingParamsModel()
    use_tqdm: bool = False


class InferenceBatchResponse(BaseModel):
    outputs: list[list[tuple[str, float]]]


class LogprobSamplingParamsModel(BaseModel):
    temperature: float = 0.0
    max_tokens: int = 2048
    top_p: float = 1.0
    n: int = 1
    logprobs: int = 1
    prompt_logprobs: int = 1


class ComputeLogprobRequest(BaseModel):
    state: str
    possible_steps: list[str]
    limit: int
    sampling_params: LogprobSamplingParamsModel
    use_tqdm: bool = False


ProverCfgT = TypeVar("ProverCfgT", bound=BaseModel)


@runtime_checkable
class ProverProtocol(Protocol[ProverCfgT]):
    """
    Interface for prover implementations.

    The term "protocol" is used because it is Python's name for defining
    interfaces under duck typing.

    Common attributes:
        config : ProverCfgT
            Prover-specific configuration type.
        logger : Logger
            Logger instance. This will be set by the evaluator during evaluation).
    """

    config: ProverCfgT
    logger: Logger

    def load_config(self, config: ProverCfgT) -> None:
        """Replace the current prover configuration."""
        ...

    def prove(self, lemma: LemmaProtocol, isa_port: int) -> list[str]:
        """
        Main interface for proving a lemma.

        The prover focuses only on the proving logic and expects the lifecycle of the REPL session to be managed by outside code (e.g., the evaluator).
        When `prove` is called, it expects a Java backend is already listening on
        `isa_port` and the REPL has stepped to just after the
        lemma statement. The prover should just connect to the gateway and start searching for a proof.
        It should also leave the cleanup of repl to the caller.
        """
        ...
