import os, sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app.services.hotpepper import budget_code_from_yen


def test_budget_code_from_yen():
    assert budget_code_from_yen(None) is None
    assert budget_code_from_yen(1500) == "B002"
    assert budget_code_from_yen(2500) == "B003"
    assert budget_code_from_yen(3500) == "B008"
    assert budget_code_from_yen(4500) == "B001"
    assert budget_code_from_yen(5500) == "B006"
