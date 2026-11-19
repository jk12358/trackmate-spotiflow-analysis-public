"""Entry point for Streamlit Community Cloud and `streamlit run streamlit_app.py`."""

import sys
from pathlib import Path

# Community Cloud installs the dependencies from uv.lock; make sure this
# repository's own package is importable even if it was not installed.
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from trackmate_spotiflow_analysis.app.page import main  # noqa: E402

main()
