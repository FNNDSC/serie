from pathlib import Path


def read_example(name: str) -> str:
    path = Path(__file__).parent / name
    return path.read_text()
