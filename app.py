"""
app.py

Streamlit interface for the UK Student Loan Repayment Simulator.
Uses loan_engine.py for all calculation logic.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from loan_engine import (
    PLAN_5,
    PLAN_2,
    annual_repayment,
    generate_salary_path,
    simulate_years,
    summarise,
)

st.set_page_config(page_title="UK Student Loan Repayment Simulator", layout="wide")

st.title("UK Student Loan Repayment Simulator")
st.caption("Models Plan 5 repayments based on 2026/27 rules. For illustration only — not financial advice.")

# --- Session state defaults (for scenario presets) ---
if "starting_salary" not in st.session_state:
    st.session_state.starting_salary = 28000
if "growth_rate_pct" not in st.session_state:
    st.session_state.growth_rate_pct = 3.0


def apply_preset(salary: float, growth: float):
    st.session_state.starting_salary = salary
    st.session_state.growth_rate_pct = growth


# --- Sidebar ---
with st.sidebar:
    st.markdown("**LOAN DETAILS**")
    plan_choice = st.selectbox(
        "Loan plan", ["Plan 5", "Plan 2"],
        help="Your plan depends on when and where you started your course — it isn't something you choose."
    )
    plan = PLAN_5 if plan_choice == "Plan 5" else PLAN_2

    st.caption(f"ℹ️ {plan['description']}")

    starting_balance = st.number_input(
        "Starting loan balance (£)", min_value=0, value=45000, step=500,
        help="The amount you currently owe. The simulation starts from this figure at Year 0."
    )

    st.divider()
    st.markdown("**INCOME**")

    st.caption("Try a scenario")
    preset_col1, preset_col2, preset_col3 = st.columns(3)
    preset_col1.button("Graduate", on_click=apply_preset, args=(28000, 3.0), use_container_width=True)
    preset_col2.button("Mid-career", on_click=apply_preset, args=(40000, 3.0), use_container_width=True)
    preset_col3.button("High earner", on_click=apply_preset, args=(60000, 4.0), use_container_width=True)

    starting_salary = st.number_input(
        "Starting salary (£)", min_value=0, step=500, key="starting_salary"
    )
    growth_rate_pct = st.slider(
        "Annual salary growth (%)", min_value=0.0, max_value=10.0, step=0.5,
        key="growth_rate_pct",
        help="The percentage your salary is assumed to increase each year. "
             "For example, 3% means a £30,000 salary becomes £30,900 the following year."
    )
    growth_rate = growth_rate_pct / 100

    st.divider()
    st.markdown("**SCENARIOS**")
    enable_overpayment = st.checkbox("Compare monthly overpayment")
    monthly_overpayment = 0
    if enable_overpayment:
        monthly_overpayment = st.slider(
            "Monthly voluntary overpayment (£)", min_value=0, max_value=500, value=100, step=10,
            help="An extra amount paid on top of your standard repayment each month."
        )

# --- Run simulations ---
salary_path = generate_salary_path(starting_salary, growth_rate, plan["write_off_years"])

standard_results = simulate_years(
    starting_balance=starting_balance,
    salary_path=salary_path,
    threshold=plan["threshold"],
    repayment_rate=plan["repayment_rate"],
    interest_rate=plan["interest_rate"],
    max_years=plan["write_off_years"],
)
standard_summary = summarise(standard_results, plan["write_off_years"])

overpay_results = []
overpay_summary = None
if enable_overpayment and monthly_overpayment > 0:
    balance = starting_balance
    for year in range(plan["write_off_years"]):
        if balance <= 0:
            break
        annual_overpay = monthly_overpayment * 12
        res = simulate_years(
            starting_balance=balance,
            salary_path=salary_path[year:],
            threshold=plan["threshold"],
            repayment_rate=plan["repayment_rate"],
            interest_rate=plan["interest_rate"],
            max_years=1,
            one_off_overpayment={"year": 0, "amount": annual_overpay},
        )
        if not res:
            break
        res[0].year = year + 1
        overpay_results.append(res[0])
        balance = res[0].balance_end
    overpay_summary = summarise(overpay_results, plan["write_off_years"])

# --- Headline metrics: Starting balance / Monthly repayment / Final outcome ---
first_year_repayment = annual_repayment(starting_salary, plan["threshold"], plan["repayment_rate"])
monthly_repayment = first_year_repayment / 12

col1, col2, col3 = st.columns(3)
col1.metric("Starting balance", f"£{starting_balance:,.0f}")
col2.metric("Est. monthly repayment", f"£{monthly_repayment:,.2f}", f"£{first_year_repayment:,.0f}/year")

if standard_summary["cleared_early"]:
    col3.metric("Final outcome", "Cleared early", f"after {standard_summary['years_taken']} years")
else:
    col3.metric("Final outcome", "Written off", f"£{standard_summary['final_balance']:,.0f} remaining")

st.caption(
    f"Total repaid: £{standard_summary['total_repaid']:,.0f} · "
    f"Total interest charged: £{standard_summary['total_interest_charged']:,.0f} · "
    f"Simulated under {plan['name']} rules"
)

st.divider()

# --- Graph: balance vs cumulative repayments, with event markers ---
st.subheader("Your repayment over time")

df_standard = pd.DataFrame([r.__dict__ for r in standard_results])
df_standard["cumulative_repaid"] = df_standard["repayment_made"].cumsum()

fig = go.Figure()
fig.add_trace(go.Scatter(
    x=df_standard["year"], y=df_standard["balance_end"],
    mode="lines", name="Remaining balance", line=dict(color="#EF553B"),
    hovertemplate="£%{y:,.0f}<extra></extra>"
))
fig.add_trace(go.Scatter(
    x=df_standard["year"], y=df_standard["cumulative_repaid"],
    mode="lines", name="Cumulative repaid", line=dict(color="#00CC96"),
    yaxis="y2",
    hovertemplate="£%{y:,.0f}<extra></extra>"
))

if enable_overpayment and monthly_overpayment > 0 and overpay_results:
    df_overpay = pd.DataFrame([r.__dict__ for r in overpay_results])
    fig.add_trace(go.Scatter(
        x=df_overpay["year"], y=df_overpay["balance_end"],
        mode="lines", name=f"Balance with £{monthly_overpayment}/mo overpayment",
        line=dict(color="#EF553B", dash="dot"),
        hovertemplate="£%{y:,.0f}<extra></extra>"
    ))

# Event markers
peak_idx = df_standard["balance_end"].idxmax()
peak_year = int(df_standard.loc[peak_idx, "year"])
if peak_year > 1:
    fig.add_vline(x=peak_year, line_dash="dot", line_color="gray",
                  annotation_text="Peak balance", annotation_position="top left")

if standard_summary["cleared_early"]:
    fig.add_vline(x=standard_summary["years_taken"], line_dash="dot", line_color="#00CC96",
                  annotation_text="Loan cleared", annotation_position="top right")
else:
    fig.add_vline(x=standard_summary["years_taken"], line_dash="dot", line_color="#EF553B",
                  annotation_text="Write-off point", annotation_position="top right")

fig.update_layout(
    xaxis_title="Year",
    yaxis=dict(title="Remaining balance (£)"),
    yaxis2=dict(title="Cumulative repaid (£)", overlaying="y", side="right"),
    hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    hoverlabel=dict(font_size=16, font_family="Arial"),
)
st.plotly_chart(fig, width="stretch")

st.divider()

# --- Repayment breakdown table ---
st.subheader("Repayment breakdown")

breakdown = pd.DataFrame({
    "Detail": [
        "Starting balance", "Starting salary", "Repayment threshold",
        "Income above threshold", "First-year repayment", "Assumed salary growth",
    ],
    "Value": [
        f"£{starting_balance:,.0f}",
        f"£{starting_salary:,.0f}",
        f"£{plan['threshold']:,.0f}",
        f"£{max(0, starting_salary - plan['threshold']):,.0f}",
        f"£{first_year_repayment:,.0f}",
        f"{growth_rate_pct:.1f}%",
    ],
})
st.table(breakdown.set_index("Detail"))

# --- Scenario comparison ---
if enable_overpayment and monthly_overpayment > 0 and overpay_results:
    st.divider()
    st.subheader("Scenario comparison")
    comp_col1, comp_col2 = st.columns(2)

    with comp_col1:
        st.markdown("**Standard repayment**")
        st.write(f"Total paid: £{standard_summary['total_repaid']:,.0f}")
        st.write(f"Loan duration: {standard_summary['years_taken']} years")

    with comp_col2:
        st.markdown(f"**With £{monthly_overpayment}/month overpayment**")
        st.write(f"Total paid: £{overpay_summary['total_repaid']:,.0f}")
        st.write(f"Loan duration: {overpay_summary['years_taken']} years")

    interest_saved = standard_summary["total_interest_charged"] - overpay_summary["total_interest_charged"]
    st.success(f"**You save approximately £{interest_saved:,.0f} in interest** by overpaying £{monthly_overpayment}/month.")

st.divider()

# --- What does this mean? ---
st.subheader("💡 What does this mean?")

rises_first = peak_year > 1
outcome_text = (
    f"the remaining balance is cleared after {standard_summary['years_taken']} years"
    if standard_summary["cleared_early"]
    else f"the remaining £{standard_summary['final_balance']:,.0f} is written off after "
         f"{plan['write_off_years']} years"
)

explanation = (
    f"Starting with a £{starting_balance:,.0f} balance and a £{starting_salary:,.0f} salary, "
    f"your income sits {'above' if starting_salary > plan['threshold'] else 'at or below'} "
    f"the £{plan['threshold']:,.0f} repayment threshold from year one. "
)
if rises_first:
    explanation += (
        f"Your balance actually **increases** for the first {peak_year} year(s) because the "
        f"interest charged exceeds what you're repaying early on. "
    )
explanation += f"As your salary grows at {growth_rate_pct:.1f}% per year, your repayments increase too, and {outcome_text}."

st.info(explanation)

st.divider()
with st.expander("Methodology & assumptions"):
    st.markdown("""
    - Assumes constant employment with no career breaks or income gaps.
    - Salary growth is modelled as a flat annual percentage, not real-world variation.
    - Interest rate is held constant at the current published rate; actual rates are reviewed annually.
    - Thresholds are held at current levels; in reality Plan 5's threshold rises with RPI from April 2027.
    - Interest is applied to the full balance before that year's repayment is deducted, matching how UK student loan interest actually accrues.
    - This tool is for illustration only and does not constitute financial advice.
    """)