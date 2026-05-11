from pathlib import Path

from pydantic import TypeAdapter

from data.lemma import Lemma
from utils.isar_utils import extract_theorem_name

FVELv2Data = dict[str, list[Lemma]]
# !NOTE: We don't make it a class inheriting from dict[str, list[Lemma]] cos in that way pydantic validation using TypeAdaptor does not work.


def find_lemma(
    data: FVELv2Data, name: str, theory: str, session: str
) -> Lemma | None:
    """
    Finds a lemma by its in-Isabelle name, theory, and session across all splits.
    """
    found = [
        lemma
        for split in data.values()
        for lemma in split
        if lemma.session == session
        and lemma.theory == theory
        and extract_theorem_name(lemma.statement) == name
    ]
    return found[0] if found else None


def load_FVELv2(fvel_lemmasV2_path: Path) -> FVELv2Data:
    """
    Load FVELv2 lemmas from the given JSON file.
    """
    return TypeAdapter(FVELv2Data).validate_json(fvel_lemmasV2_path.read_bytes())


if __name__ == "__main__":
    ## Load FVELv2 lemmas and print the size of each split
    from eval.config import DATASET_LEMMA_SPLIT_PATH

    fvel_data = load_FVELv2(Path(DATASET_LEMMA_SPLIT_PATH))
    print(
        f"FVELv2 train size: {len(fvel_data['train']) if 'train' in fvel_data else None}"
    )
    print(
        f"FVELv2 test size: {len(fvel_data['test']) if 'test' in fvel_data else None}"
    )
    print(
        f"FVELv2 test_hard size: {len(fvel_data['test_hard']) if 'test_hard' in fvel_data else None}"
    )
