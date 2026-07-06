import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import yaml, pytest

@pytest.fixture
def cfg():
    with open(os.path.join(os.path.dirname(__file__), "..", "config", "config.yaml")) as f:
        return yaml.safe_load(f)
