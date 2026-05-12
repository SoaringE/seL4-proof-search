from collections.abc import Mapping
from logging import Logger
from pathlib import Path
from typing import Any, Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel, ConfigDict

try:
    from vllm.inputs import PromptType
except ImportError:
    PromptType = Any

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

    def prove(
        self,
        lemma: LemmaProtocol,
        isa_port: int,
        session_root: Path,
        exclude_list: list[str] = [],
        repl_envs: Mapping[str, str | None] = {},
    ) -> list[str]:
        """
        Main interface for proving a lemma.

        The prover owns the Isabelle REPL JAR for the duration of this call:
        it must start a JAR listening on `isa_port`, initialize the theory file
        for `lemma`, step to just after the lemma statement, search for a proof,
        and shut the JAR down before returning.

        Args:
            lemma: the lemma to prove.
            isa_port: port on which the prover should bring up its own JAR.
            session_root: absolute root directory of the Isabelle session
                (e.g. the l4v checkout). Used to resolve `lemma.path`.
            exclude_list: absolute paths of theory files that must NOT be
                replaced by sorry during prefix execution.
            repl_envs: environment variables to pass to the JAR subprocess.
        """
        ...
