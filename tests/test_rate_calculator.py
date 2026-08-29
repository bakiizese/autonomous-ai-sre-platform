import pytest
from rate_calculator import calculate_rate

def test_calculate_rate_zero_count():
    assert calculate_rate(100, 0) == 0.0

def test_calculate_rate_valid_count():
    assert calculate_rate(100, 4) == 25.0