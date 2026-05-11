from typing import (
    Annotated,
    Union,
)

from pydantic import BaseModel, DirectoryPath, Field

from data.lemma import Context, Lemma, LemmaFVEL, new_Lemma_from_FVEL
from data.lib import OptionalRelPathField, RelPath, RelPathField


class Theory(BaseModel):
    """Represents an Isabelle theory file with its dependencies and contents."""

    name: str = Field(
        description="Name of the theory file.",
    )
    dependency: dict[str, OptionalRelPathField] = Field(
        default={},
        description="Dictionary of dependencies, where keys are import patterns and values are paths to the dependent theory files.",
    )
    depth: int = Field(
        default=-1,
        description="The depth of the theory in the dependency graph.",
    )
    child: list[RelPath] = Field(
        default=[],
        description="List of paths to child theory files that import this theory.",
    )
    path: RelPath = Field(
        description="Path to the theory file, relative to some base directory.",
    )
    session: str = ""
    cells: list[Annotated[Union[Lemma, Context], Field(discriminator="tag")]] = Field(
        default=[], description="List of lemmas and contexts defined in this theory."
    )
    session_dir: OptionalRelPathField = Field(
        default=None,
        description="Directory of the session, relative to the base directory.",
    )

    base_dir: DirectoryPath | None = Field(
        default=None,
        description="Base directory for relative paths in this object.",
        exclude=True,
    )

    def get_lemmas(self) -> list[Lemma]:
        """Get all lemmas defined in this theory."""
        return [cell for cell in self.cells if cell.tag == "lemma"]  # type: ignore[return-value]


class TheoryFVEL(BaseModel):
    """
    Python model for validating Isabelle theory files in FVEL format.

    An example:
    ```
    {
        "name": "More_Arithmetic",
        "dependency": {
            "Main": "",
            "HOL-Library.Type_Length": ""
        },
        "depth": 1,
        "related_c_code": [],
        "child": [
            "/lib/Word_Lib/More_Word.thy",
            "/lib/Word_Lib/Most_significant_bit.thy",
            "/lib/Word_Lib/Bitwise.thy",
            "/lib/Word_Lib/Word_Lib_Sumo.thy"
        ],
        "path": "/lib/Word_Lib/More_Arithmetic.thy",
        "session": "Word_Lib",
        "lemmas": []
    }
    ```
    """

    name: str
    dependency: dict[str, OptionalRelPathField] = Field(
        default={},
        description="Dictionary of dependencies, where keys are import patterns and values are paths to the dependent theory files.",
    )
    depth: int = Field(
        default=-1,
        description="The depth of the theory in the dependency graph.",
    )
    child: list[RelPathField] = Field(
        default=[],
        description="List of paths to child theory files that import this theory.",
    )
    path: RelPathField
    session: str
    lemmas: list[LemmaFVEL] = Field(
        default=[],
        description="List of lemmas defined in this theory.",
    )


def new_Theory_from_FVEL(data: TheoryFVEL) -> Theory:
    """
    Creates a Theory instance from a dictionary in FVEL format.
    """
    thy = Theory(
        name=data.name,
        dependency=data.dependency,
        depth=data.depth,
        child=data.child,
        path=data.path,
        session=data.session,
        cells=[new_Lemma_from_FVEL(lemma) for lemma in data.lemmas],
    )
    # For each cell, update its session and path to match the theory
    for cell in thy.cells:
        cell.session = thy.session
        cell.path = thy.path
    return thy
