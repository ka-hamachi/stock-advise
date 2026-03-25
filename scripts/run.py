#!/usr/bin/env python3
"""Entry point for stock-advise system."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.scheduler import main

if __name__ == "__main__":
    main()
