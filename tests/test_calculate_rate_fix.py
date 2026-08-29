import pytest
from my_module import calculate_rate

def test_calculate_rate_zero_count_returns_zero():
    """Verify that calculate_rate returns 0.0 when count is zero."""
    assert calculate_rate(100, 0) == 0.0

def test_calculate_rate_normal_operation():
    """Verify that calculate_rate works correctly for valid inputs."""
    assert calculate_rate(100, 10) == 10.0
    assert calculate_rate(50, 5) == 10.0

def test_calculate_rate_zero_total():
    """Verify that calculate_rate returns 0.0 when total is zero and count is non-zero."""
    assert calculate_rate(0, 10) == 0.0

def test_calculate_rate_negative_values():
    """Verify that calculate_rate handles negative values correctly."""
    assert calculate_rate(-100, 10) == -10.0
    assert calculate_rate(100, -10) == -10.0