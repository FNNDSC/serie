from pathlib import Path

__file = Path(__file__).parent / "version.txt"
__version__ = __file.read_text() if __file.exists() else "0.0.0-unknown"
