import random
import os
import sys
import pytest

# Ensure the project root is on the module search path when the package is not
# installed. This allows ``import simulateur_lora_sfrd`` to succeed during
# test collection without requiring an editable installation.
ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

@pytest.fixture(autouse=True)
def _set_seed():
    random.seed(1)
