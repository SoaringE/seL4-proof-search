from pathlib import Path
from typing import Annotated, Dict, Generic, List, Literal, Optional, TypeVar

from pydantic import (
    AfterValidator,
    BaseModel,
    DirectoryPath,
    Field,
    FilePath,
    PositiveInt,
)

import eval.config as config
from data.lib import OptionalRelPathField

__all__ = [
    "ProverCfgT",
    "LoggingConfig",
    "BaseEvalConfig",
]


ProverCfgT = TypeVar("ProverCfgT", bound=BaseModel)


class LoggingConfig(BaseModel):
    """Logging configuration for the evaluator.

    Attributes:
        log_dir: Directory to save log files (created if doesn't exist)
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file. Can be:
            - None: auto-generate as <log_dir>/<prover_name>-MMDD-HHMM.log
            - str/Path: relative paths are relative to log_dir, absolute paths used as-is
        format: Python logging format string
        to_console: Whether to output logs to console
        to_file: Whether to output logs to file
    """

    log_dir: Annotated[
        Path, AfterValidator(lambda p: p.mkdir(parents=True, exist_ok=True))
    ] = Field(
        default=Path("logs"),
        description="Directory to save log files (created if doesn't exist)",
    )

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", description="Logging level"
    )
    log_file: OptionalRelPathField = Field(
        default=None, description="None or path of the log file relative to log_dir. "
    )
    format: str = Field(
        default="[%(asctime)s - %(levelname)s - %(ctx)s] %(message)s",
        description="Python logging format string. It may include %(ctx)s as a placeholder for the context (EVAL or PROVER).",
    )
    to_stdout: bool = Field(
        default=True, description="Whether to output logs to console."
    )
    to_file: bool = Field(default=True, description="Whether to output logs to file")


class BaseEvalConfig(BaseModel, Generic[ProverCfgT]):
    server_num: int
    start_port: PositiveInt
    check_point: Optional[FilePath] = Field(
        default=None, description="Path to the checkpoint file"
    )
    timeout: PositiveInt = Field(
        description="Timeout for each proof verification in seconds"
    )
    save_path: Path = Field(
        default=Path("output/eval_results.json"),
        description="File path to save the evaluation results",
    )
    llm_address: str = Field(description="Address of the LLM server")

    session_root: DirectoryPath = Field(
        default=Path(config.SESSION_ROOT),
        description="Root directory of Isabelle sessions",
    )
    execute_batch_size: PositiveInt = Field(
        default=config.EXECUTE_BATCH_SIZE,
    )
    exclude_list: List[str] = Field(
        default=[
            "spec/take-grant/Example2.thy",
            "lib/EVTutorial/EquivValidTutorial.thy",
            "lib/test/Apply_Debug_Test.thy",
            "lib/test/FastMap_Test.thy",
            "lib/test/RangeMap_Test.thy",
            "lib/test/FP_Eval_Tests.thy",
            "lib/test/CorresK_Test.thy",
        ],
        description="List of paths to theory files to exclude, relative to session_root",
    )
    custom_env: Dict[str, str | None] = Field(
        default={}, description="Custom environment variables during evaluation."
    )

    logging_config: LoggingConfig = Field(
        description="Logging configuration. See LoggingConfig for details.",
        default_factory=LoggingConfig,
    )

    prover_config: Optional[ProverCfgT] = Field(
        default=None, description="Configuration for the prover"
    )

    def get_abs_excludes(self) -> List[str]:
        return [str(self.session_root / p) for p in self.exclude_list]
