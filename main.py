"""
Convenience entry point for running directly from the project root.

Preferred:          uv run pctester
Also works:         uv run python main.py
Without UV (dev):   python main.py  (requires dependencies already installed)
"""

from src.cli import main

if __name__ == "__main__":
    main()
