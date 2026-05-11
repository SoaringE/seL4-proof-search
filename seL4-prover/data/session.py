import os
from collections.abc import MutableMapping
from pathlib import Path, PurePath
from typing import Literal, TypeAlias

from pydantic import BaseModel, DirectoryPath, Field

from data.lib import RelPath, RelPathField
from utils.lib import listDedup, normalizeIsarPathPattern, remove_quotes


def match_thy(thy_path: PurePath, pattern: str) -> bool:
    """
    Match a theory file path against a pattern string.

    The pattern can be:
    - SomeThy
    - SomeThy.thy (or .ML)
    - dir/SomeThy
    - dir/SomeThy.thy
    - $SOME_ENV/SomeThy

    Returns True if the theory path matches the suffix pattern.
    """

    ## We match the path by the suffix of the complete path
    suffix: str = normalizeIsarPathPattern(pattern)
    if not suffix.endswith(".thy"):
        suffix += ".thy"
    return thy_path.match(suffix)


ThyTag: TypeAlias = Literal[
    "EXPLICIT",  # Listed in the session's ROOT file
    "IMPLICIT_IMPORT",  # Imported by an explict theory in the session but are not listed in the session's ROOT file
    "IMPLICIT_EXPORT",  # Dependent by a downstream session but is not tagged EXPLICIT in the current session
    "UNREFED",  # Not referenced by any session but is found in the session's directories
    "INCLUDED",  # Either EXPLICIT, IMPLICIT_IMPORT, or IMPLICIT_EXPORT
]


class Session(BaseModel):
    """
    Data structure for Isabelle session information including theory dependencies.

    Manages session metadata, theory lists with tags, directory structure,
    and dependency relationships between sessions.
    """

    class TaggedThy(BaseModel):
        """
        Represents a theory file with its path and classification tag.
        """

        path: RelPath
        tag: ThyTag = "UNREFED"

    name: str
    theories: list[TaggedThy] = Field(
        default=[],
        description="All .thys found in the session's directories with their tags.",
    )

    dependency: list[str] = Field(
        default=[],
        description="List of dependent sessions.",
    )
    base_dir: DirectoryPath | None = Field(
        default=None,
        description="The base directory of the session. ROOT_dir field or theory dirs are relative to this dir.",
        exclude=True,
    )
    ROOT_dir: RelPath = Field(
        description="The dir containing the ROOT file, relative to `base_dir`.",
    )
    dirs: list[RelPath] = Field(
        default=[RelPath(".")],
        description="All dirs that contain theories, relative to `ROOT_dir`. The first dir is the main session dir i.e. the dir behind the `in` keyword in the ROOT file.",
    )
    depth: int = Field(
        default=0,
        description="The depth of the session in the dependency graph. 1 means no dependencies except built-in sessions.",
    )

    def get_all_dirs(self) -> list[RelPath]:
        """
        Get all directories in the session relative to the base directory.
        """
        return [self.ROOT_dir / d for d in self.dirs]

    def set_base_dir(self, base_dir: Path):
        """
        Set the base directory of the session.
        """
        assert base_dir.is_dir(), f"{base_dir} is not a directory."
        self.base_dir = base_dir.resolve()

    def find_all_thys(self) -> list[RelPath]:
        """
        Find all *.thy and *.ML files in the session's directories relative to the L4V path.

        """
        if not self.base_dir:
            raise ValueError("Base directory is not set.")
        return [
            Path(os.path.normpath(p)).relative_to(self.base_dir)
            for d in self.get_all_dirs()
            for p in [
                *(self.base_dir / d).glob("*.thy", case_sensitive=False),
                *(self.base_dir / d).glob("*.ML", case_sensitive=False),
            ]
        ]

    def query_thy(self, thy: str) -> list[TaggedThy]:
        """
        Query the session's theories for a given theory name.
        """
        return [t for t in self.theories if match_thy(t.path, thy)]


class SessionFVEL(BaseModel):
    """
    Pydantic model for validating FVEL session data.

    Example:
    {
        "dependency": ["CKernel"],
        "name": "CSpec",
        "theories": [
            "/spec/cspec/c/build/ARM/generated/sel4/shared_types_proofs.thy",
            "/spec/cspec/Substitute.thy",
            ...
        ],
        "ROOT_dir": "spec",
        "ROOT_relative_dir": "cspec",
        "additional_dir": [
            ".",
            "c/build/ARM/generated/arch/object",
            "c/build/ARM/generated/sel4"
        ],
        "depth": 8
    }
    """

    dependency: list[str] = Field(
        default_factory=list, description="List of dependent session names."
    )
    name: str
    theories: list[RelPathField] = Field(
        default_factory=list, description="List of theory file paths."
    )
    ROOT_dir: RelPathField = Field(
        ..., description="Directory containing the ROOT file."
    )
    ROOT_relative_dir: RelPathField = Field(
        default=RelPath("."), description="Session directory relative to ROOT_dir."
    )
    additional_dir: list[RelPathField] = Field(
        default_factory=list,
        description="Additional directories to search for theories.",
    )
    depth: int | None = Field(
        default=0, description="Depth of the session in the dependency graph."
    )


def new_Session_from_FVEL(data: SessionFVEL) -> Session:
    fake_base_dir = Path("/fake/base")
    norm_dirs = [
        (fake_base_dir / data.ROOT_dir / data.ROOT_relative_dir / d).resolve() for d in data.additional_dir
    ] # NOTE: The `additional_dir` in FVEL actually contains "." as the 1st entry so it already includes all dirs used in the session.

    return Session(
        name=data.name,
        theories=[
            Session.TaggedThy(path=PurePath(t), tag="INCLUDED") for t in data.theories
        ],
        dependency=data.dependency,
        ROOT_dir=data.ROOT_dir,
        dirs=[
            p.relative_to(fake_base_dir / data.ROOT_dir) for p in listDedup(norm_dirs)
        ],
        depth=data.depth if data.depth is not None else 0,
    )


def safely_unquote_session_names(
    data: MutableMapping[str, Session | SessionFVEL],
) -> None:
    """
    Unquote session names if their unquoted form appears somewhere in the data (either as a session name or a dependency).
    """
    should_remove_quotes: set[str] = set(
        s
        for s in list(data.keys()) + [t for v in data.values() for t in v.dependency]
        if s == remove_quotes(s)
    )
    for k, session in data.items():
        k_unquoted = remove_quotes(k)
        if k_unquoted != k and k_unquoted in should_remove_quotes:
            data[k_unquoted] = session
            del data[k]
            session.name = k_unquoted
        session.dependency = [
            remove_quotes(s) if remove_quotes(s) in should_remove_quotes else s
            for s in session.dependency
        ]
