import pytest
from math_helpers import calculate_rate

def test_calculate_rate_valid():
    assert calculate_rate(100, 5) == 20.0

def test_calculate_rate_zero_count():
    assert calculate_rate(100, 0) == 0.0
