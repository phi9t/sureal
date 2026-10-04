#!/usr/bin/env python3
"""Run the documented architecture experiments with the live Insula harness."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent/'architecture'))
from experiment_runner import main
raise SystemExit(main())
