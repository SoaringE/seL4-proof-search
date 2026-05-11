from pathlib import Path
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, DirectoryPath, Field

from data.lib import OptionalRelPathField, RelPath


class ProofStep(BaseModel):
    """Represents a single step in a proof, including the line of code and the resulting state."""

    step: str = Field(
        default="",
        description="The line of code representing the proof step.",
    )
    state: str | None = Field(
        default=None,
        description="The state of the proof after applying this step.",
    )


class Cell(BaseModel):
    """
    Metadata common to both Lemma and Context.
    """

    theory: str = Field(
        default="",
        description="The name of the theory",
    )
    session: str = ""
    path: OptionalRelPathField = Field(
        default=None,
        description="Path to the theory file where the cell is defined, relative to some base directory.",
    )

    base_dir: DirectoryPath | None = Field(
        default=None,
        description="Base directory for relative paths.",
    )

    def getAbsPath(self, base_dir: DirectoryPath | None = None) -> Path | None:
        if base_dir is None:
            base_dir = self.base_dir
        return (
            base_dir / self.path
            if base_dir is not None and self.path is not None and base_dir.is_absolute()
            else None
        )


@runtime_checkable
class LemmaProtocol(Protocol):
    """Protocol for lemma objects."""

    theory: str
    session: str
    path: RelPath | None
    base_dir: DirectoryPath | None
    name: str
    statement: str

    def getAbsPath(self, base_dir: DirectoryPath | None = None) -> Path | None: ...


class PureLemma(Cell):
    name: str
    statement: str = ""


class Lemma(PureLemma):
    """Represents a lemma with its metadata and proof content."""

    tag: Literal["lemma"] = Field(
        default="lemma",
        frozen=True,
        description="The tag of the lemma, fixed to 'lemma'.",
    )
    proof: list[ProofStep] = Field(
        default=[],
        description="List of proof steps with line and the state after applying the step.",
    )
    num_steps: int = Field(
        default=-1,
        description="Number of steps in the proof.",
    )
    source: str | None = Field(
        default=None,
        description="The dataset this lemma belongs to.",
    )

    def dump_pure_lemma(self) -> dict[str, Any]:
        """
        Dump the lemma as a dictionary with only the fields in LemmaProtocol.
        """
        return {
            k: v
            for k, v in self.model_dump().items()
            if k in LemmaProtocol.__annotations__
        }


class LemmaFVEL(BaseModel):
    """
    Python model for validating lemmas in FVEL format.

    An example:
    ```
    {
        "session": "",
        "dependency": [],
        "context": "lemma n_less_equal_power_2:\\n  \\"n < 2 ^ n\\" by (fact less_exp)",
        "proof": [
            "lemma n_less_equal_power_2:\\n  \\"n < 2 ^ n\\"",
            "by (fact less_exp)"
        ],
        "proof_state": [
            "proof (prove)\\ngoal (1 subgoal):\\n 1. n < 2 ^ n",
            ""
        ],
        "statement": "lemma n_less_equal_power_2:\\n  \\"n < 2 ^ n\\"",
        "name": "unnamed_thy_1",
        "theory_name": "More_Arithmetic",
        "num_steps": 1
    }
    ```
    """

    name: str
    statement: str
    proof: list[str] = Field(
        default=[],
        description="List of proof steps as strings.",
    )
    proof_state: list[str] = Field(
        default=[],
        description="List of proof states as strings after each step.",
    )
    theory_name: str
    num_steps: int = 0


class Context(Cell):
    tag: Literal["context"] = Field(
        default="context",
        frozen=True,
        description="The tag of the context, fixed to 'context'.",
    )
    text: str = ""


def new_Lemma_from_FVEL(data: LemmaFVEL) -> Lemma:
    """
    Creates a Lemma instance from a dictionary in FVEL format.

    An example:
    ```
    {
        "session": "",
        "dependency": [],
        "context": "lemma n_less_equal_power_2:\\n  \\"n < 2 ^ n\\" by (fact less_exp)",
        "proof": [
            "lemma n_less_equal_power_2:\\n  \\"n < 2 ^ n\\"",
            "by (fact less_exp)"
        ],
        "proof_state": [
            "proof (prove)\\ngoal (1 subgoal):\\n 1. n < 2 ^ n",
            ""
        ],
        "statement": "lemma n_less_equal_power_2:\\n  \\"n < 2 ^ n\\"",
        "name": "unnamed_thy_1",
        "theory_name": "More_Arithmetic",
        "num_steps": 1
    }
    ```

    """
    proof: list[ProofStep] = []
    if len(data.proof) == len(data.proof_state):
        proof = [
            ProofStep(step=step, state=state)
            for step, state in list(zip(data.proof, data.proof_state))[1:]
        ]

    lemma = Lemma(
        name=data.name,
        statement=data.statement,
        theory=data.theory_name,
        proof=proof,
        num_steps=len(proof),
    )

    return lemma
