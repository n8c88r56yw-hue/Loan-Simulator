"""
test_loan_engine.py

Unit tests for the loan calculation engine, covering the key edge cases:
- Salary below/at/above the repayment threshold
- A salary path that clears the loan before write-off
- A salary path that reaches write-off with balance remaining
- A one-off overpayment reducing the total interest paid
"""

import pytest
from loan_engine import (
    PLAN_5,
    annual_repayment,
    apply_interest,
    generate_salary_path,
    simulate_years,
    summarise,
)


# --- annual_repayment tests ---

def test_repayment_is_zero_below_threshold():
    result = annual_repayment(salary=20000, threshold=25000)
    assert result == 0.0


def test_repayment_is_zero_exactly_at_threshold():
    result = annual_repayment(salary=25000, threshold=25000)
    assert result == 0.0


def test_repayment_above_threshold():
    # £5,000 above threshold, at 9% = £450
    result = annual_repayment(salary=30000, threshold=25000, rate=0.09)
    assert result == 450.0


# --- apply_interest tests ---

def test_interest_calculation():
    result = apply_interest(balance=10000, annual_rate=0.032)
    assert result == 320.0


def test_interest_on_zero_balance():
    result = apply_interest(balance=0, annual_rate=0.032)
    assert result == 0.0


# --- generate_salary_path tests ---

def test_salary_path_length():
    path = generate_salary_path(starting_salary=25000, growth_rate=0.03, years=5)
    assert len(path) == 5


def test_salary_path_grows_correctly():
    path = generate_salary_path(starting_salary=100, growth_rate=0.10, years=3)
    # Year 0: 100, Year 1: 110, Year 2: 121
    assert path[0] == 100
    assert path[1] == 110.0
    assert path[2] == 121.0


# --- simulate_years tests: clearing before write-off ---

def test_high_salary_clears_loan_before_write_off():
    # Very high, fast-growing salary should clear a modest loan quickly
    salary_path = generate_salary_path(starting_salary=80000, growth_rate=0.05, years=40)
    results = simulate_years(
        starting_balance=5000,
        salary_path=salary_path,
        threshold=PLAN_5["threshold"],
        repayment_rate=PLAN_5["repayment_rate"],
        interest_rate=PLAN_5["interest_rate"],
        max_years=40,
    )
    summary = summarise(results, write_off_years=40)
    assert summary["cleared_early"] is True
    assert summary["final_balance"] <= 0
    assert summary["years_taken"] < 40


# --- simulate_years tests: reaching write-off ---

def test_low_salary_reaches_write_off_with_balance_remaining():
    # Low, flat salary against a large loan should hit the 40-year cap
    salary_path = generate_salary_path(starting_salary=26000, growth_rate=0.0, years=40)
    results = simulate_years(
        starting_balance=60000,
        salary_path=salary_path,
        threshold=PLAN_5["threshold"],
        repayment_rate=PLAN_5["repayment_rate"],
        interest_rate=PLAN_5["interest_rate"],
        max_years=40,
    )
    summary = summarise(results, write_off_years=40)
    assert summary["years_taken"] == 40
    assert summary["cleared_early"] is False
    assert summary["final_balance"] > 0


# --- simulate_years tests: overpayment ---

def test_overpayment_reduces_total_interest():
    salary_path = generate_salary_path(starting_salary=30000, growth_rate=0.03, years=40)

    standard = simulate_years(
        starting_balance=40000,
        salary_path=salary_path,
        threshold=PLAN_5["threshold"],
        repayment_rate=PLAN_5["repayment_rate"],
        interest_rate=PLAN_5["interest_rate"],
        max_years=40,
    )
    standard_summary = summarise(standard, write_off_years=40)

    with_overpayment = simulate_years(
        starting_balance=40000,
        salary_path=salary_path,
        threshold=PLAN_5["threshold"],
        repayment_rate=PLAN_5["repayment_rate"],
        interest_rate=PLAN_5["interest_rate"],
        max_years=40,
        one_off_overpayment={"year": 0, "amount": 5000},
    )
    overpayment_summary = summarise(with_overpayment, write_off_years=40)

    assert overpayment_summary["total_interest_charged"] < standard_summary["total_interest_charged"]


# --- edge case: zero starting balance ---

def test_zero_starting_balance_produces_no_years():
    salary_path = generate_salary_path(starting_salary=30000, growth_rate=0.03, years=40)
    results = simulate_years(
        starting_balance=0,
        salary_path=salary_path,
        threshold=PLAN_5["threshold"],
        repayment_rate=PLAN_5["repayment_rate"],
        interest_rate=PLAN_5["interest_rate"],
        max_years=40,
    )
    assert results == []