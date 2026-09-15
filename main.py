"""Entry point: python main.py [--diag] [--lang fr]"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from androidcontextdeploy.app import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
