from pathlib import Path, PurePath
from typing import Annotated, TypeAlias

from pydantic import BeforeValidator, PlainSerializer

RelPath: TypeAlias = PurePath  # A path-like object that is not absolute.


def str2rel_path(v):
    """
    If the input is an absolute path, convert it to a relative path by removing the leading '/'.
    """
    if PurePath(v).is_absolute():
        return str(v)[1:]
    return v


RelPathField: TypeAlias = Annotated[
    RelPath, BeforeValidator(str2rel_path), PlainSerializer(str)
]

OptionalRelPathField: TypeAlias = Annotated[
    RelPath | None,
    BeforeValidator(lambda x: str2rel_path(x) if x else None),
    PlainSerializer(lambda v: str(v), when_used="unless-none"),
]

OptionalPathField: TypeAlias = Annotated[
    Path | None,
    BeforeValidator(lambda x: x if x else None),
    PlainSerializer(lambda v: str(v), when_used="unless-none"),
]
