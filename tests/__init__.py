# Sorph's modules live in sorph/; make them importable by name, as flow.py does
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "sorph"))
