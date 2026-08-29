import pytest
from calculator import calculate_rate

def test_calculate_rate_normal():
    assert calculate_rate(10, 2) == 5.0

def test_calculate_rate_zero_division():
    assert calculate_rate(10, 0) == 0.0