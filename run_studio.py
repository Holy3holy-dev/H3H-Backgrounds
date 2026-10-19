#!/usr/bin/env python3
import sys
from pathlib import Path

# Add studio directory to path
studio_dir = Path(__file__).parent / "studio"
sys.path.insert(0, str(studio_dir))

from h3h_studio.main import main

if __name__ == "__main__":
    main()
