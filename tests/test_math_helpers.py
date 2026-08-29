import pytest
from math_helpers import calculate_rate

def test_calculate_rate_zero_count():
    assert calculate_rate(100, 0) == 0.0

def test_calculate_rate_normal():
    assert calculate_rate(100, 2) == 50.0