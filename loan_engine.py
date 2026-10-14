"""
loan_engine.py

Core calculation logic for UK student loan repayment simulation.
Currently supports Plan 5 (and Plan 2 for comparison purposes).
Kept separate from any UI code so it can be unit tested independently.
"""

from dataclasses import dataclass, field
from typing import List, Optional


# --- Plan definitions (2026/27 tax year figures) ---

PLAN_5 = {
    "name": "Plan 5",
    "threshold": 25000,      # £ per year, fixed until April 2027
    "repayment_rate": 0.09,  # 9% on income above threshold
    "interest_rate": 0.032,  # RPI only, no added margin
    "write_off_years": 40,
    "description": "For English students who started their course on or after 1 August 2023. "
                   "Lower threshold, cheaper interest (RPI only), longer 40-year write-off.",
}

PLAN_2 = {
    "name": "Plan 2",
    "threshold": 29385,
    "repayment_rate": 0.09,
    "interest_rate": 0.062,  # RPI + up to 3%, capped at 6% for 2026/27
    "write_off_years": 30,
    "description": "For English students who started their course between September 2012 and July 2023. "
                   "Higher threshold, but interest can run up to 3% above RPI, and a shorter 30-year write-off.",
}


@dataclass
class YearResult:
    year: int
    salary: float
    interest_charged: float
    repayment_made: float
    balance_start: float
    balance_end: float


def annual_repayment(salary: float, threshold: float, rate: float = 0.09) -> float:
    """
    Calculate the annual repayment amount given a salary and plan threshold.
    Returns 0 if salary is at or below the threshold.
    """
    if salary <= threshold:
        return 0.0
    return round((salary - threshold) * rate, 2)


def apply_interest(balance: float, annual_rate: float) -> float:
    """
    Apply a year's interest to the outstanding balance.
    Interest accrues on the balance before that year's repayment is deducted,
    matching how UK student loan interest is actually applied.
    """
    return round(balance * annual_rate, 2)


def generate_salary_path(
    starting_salary: float,
    growth_rate: float,
    years: int
) -> List[float]:
    """
    Generate a simple salary trajectory assuming constant annual growth.
    growth_rate is a decimal, e.g. 0.03 for 3% annual growth.
    """
    return [round(starting_salary * ((1 + growth_rate) ** year), 2) for year in range(years)]


def simulate_years(
    starting_balance: float,
    salary_path: List[float],
    threshold: float,
    repayment_rate: float,
    interest_rate: float,
    max_years: int = 40,
    one_off_overpayment: Optional[dict] = None,
) -> List[YearResult]:
    """
    Simulate the loan balance year by year until it's cleared or max_years is reached.

    one_off_overpayment: optional dict like {"year": 5, "amount": 2000} to model
    a lump-sum overpayment in a specific year.

    Returns a list of YearResult records, one per year simulated.
    """
    results = []
    balance = starting_balance

    for year in range(max_years):
        if balance <= 0:
            break

        balance_start = balance

        # Get salary for this year (repeat last known salary if path runs out)
        salary = salary_path[year] if year < len(salary_path) else salary_path[-1]

        # Interest accrues first
        interest = apply_interest(balance, interest_rate)
        balance += interest

        # Then repayment is deducted
        repayment = annual_repayment(salary, threshold, repayment_rate)

        # Apply one-off overpayment if this is the matching year
        if one_off_overpayment and one_off_overpayment.get("year") == year:
            repayment += one_off_overpayment.get("amount", 0)

        # Don't let repayment overshoot the balance
        repayment = min(repayment, balance)
        balance -= repayment
        balance = round(balance, 2)

        results.append(YearResult(
            year=year + 1,
            salary=salary,
            interest_charged=interest,
            repayment_made=repayment,
            balance_start=balance_start,
            balance_end=balance,
        ))

    return results


def summarise(results: List[YearResult], write_off_years: int) -> dict:
    """
    Produce headline figures from a simulation run: total repaid, total interest,
    and whether the loan was cleared before write-off.
    """
    total_repaid = round(sum(r.repayment_made for r in results), 2)
    total_interest = round(sum(r.interest_charged for r in results), 2)
    years_run = len(results)
    cleared = years_run < write_off_years and results and results[-1].balance_end <= 0

    return {
        "total_repaid": total_repaid,
        "total_interest_charged": total_interest,
        "years_taken": years_run,
        "cleared_early": cleared,
        "final_balance": results[-1].balance_end if results else 0,
    }


# --- Quick manual test when running this file directly ---
if __name__ == "__main__":
    plan = PLAN_5
    salary_path = generate_salary_path(starting_salary=28000, growth_rate=0.03, years=40)

    results = simulate_years(
        starting_balance=45000,
        salary_path=salary_path,
        threshold=plan["threshold"],
        repayment_rate=plan["repayment_rate"],
        interest_rate=plan["interest_rate"],
        max_years=plan["write_off_years"],
    )

    summary = summarise(results, plan["write_off_years"])

    print(f"--- {plan['name']} simulation ---")
    for r in results[:5]:
        print(r)
    print("...")
    print(summary)