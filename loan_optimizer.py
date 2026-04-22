"""
╔══════════════════════════════════════════════════════════════════╗
║           LOAN PAYOFF OPTIMIZER                                  ║
║           Built for financial freedom seekers                    ║
║                                                                  ║
║  Features:                                                       ║
║  1. Configurable loan inputs (amount, tenure, rate)              ║
║  2. Early payment options (lump sum, quarterly, monthly extra)   ║
║  3. Ad-hoc / erratic payments at any point in time               ║
║  4. Payoff time comparison                                       ║
║  5. Monthly installment impact                                   ║
║  6. Interest saved calculator                                    ║
║  7. Full amortization schedule                                   ║
║  8. Visual charts and comparisons                                ║
║                                                                  ║
║  Run: streamlit run loan_optimizer.py                             ║
╚══════════════════════════════════════════════════════════════════╝
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import math
from dataclasses import dataclass, field
from typing import Optional


# ─────────────────────────────────────────────
# DATA MODELS
# ─────────────────────────────────────────────

@dataclass
class LoanConfig:
    """Loan parameters."""
    principal: float
    annual_rate: float
    term_years: int
    initial_lump_sum: float = 0
    extra_monthly: float = 0
    quarterly_payment: float = 0
    adhoc_payments: dict = field(default_factory=dict)  # {month_number: amount}
    fixed_emi: bool = False  # True = car loan style (EMI stays fixed, tenure shrinks)


@dataclass
class MonthDetail:
    """Single month in amortization schedule."""
    month: int
    payment: float
    principal_paid: float
    interest_paid: float
    extra_paid: float
    adhoc_paid: float
    balance: float
    cumulative_interest: float
    cumulative_paid: float
    current_emi: float = 0  # EMI for this month (may change after extra payments)


@dataclass
class LoanResult:
    """Full calculation result."""
    monthly_payment: float  # initial EMI (at start of loan)
    current_emi: float  # latest recalculated EMI (after all extra payments)
    total_interest: float
    total_paid: float
    total_months: int
    schedule: list
    total_extra_paid: float
    total_adhoc_paid: float


# ─────────────────────────────────────────────
# CORE CALCULATION ENGINE
# ─────────────────────────────────────────────

def calculate_base_payment(principal: float, annual_rate: float, term_years: int) -> float:
    """Calculate standard monthly EMI using amortization formula."""
    if principal <= 0 or annual_rate <= 0:
        return 0
    r = annual_rate / 100 / 12
    n = term_years * 12
    return principal * (r * (1 + r) ** n) / ((1 + r) ** n - 1)


def calculate_loan(config: LoanConfig) -> LoanResult:
    """
    Full amortization calculation with all payment types.
    
    Supports:
    - Initial lump sum (reduces principal before amortization)
    - Extra monthly payments (applied every month)
    - Quarterly payments (applied every 3 months)
    - Ad-hoc payments (applied at specific months)
    """
    adjusted_principal = max(0, config.principal - config.initial_lump_sum)
    if adjusted_principal <= 0:
        return LoanResult(0, 0, 0, config.initial_lump_sum, 0, [], 0, 0)

    r = config.annual_rate / 100 / 12
    n = config.term_years * 12
    base_payment = adjusted_principal * (r * (1 + r) ** n) / ((1 + r) ** n - 1)
    initial_payment = base_payment  # save the starting EMI

    balance = adjusted_principal
    total_interest = 0
    total_paid = 0
    total_extra = 0
    total_adhoc = 0
    schedule = []

    month = 0
    while balance > 0.01 and month < 600:  # Safety cap at 50 years
        month += 1
        interest = balance * r

        # Base principal from current EMI
        base_principal = base_payment - interest

        # Extra monthly payment
        extra = min(config.extra_monthly, balance - base_principal) if config.extra_monthly > 0 else 0

        # Quarterly payment
        q_pay = 0
        if config.quarterly_payment > 0 and month % 3 == 0:
            q_pay = min(config.quarterly_payment, balance - base_principal - extra)
            if q_pay < 0:
                q_pay = 0

        # Ad-hoc payment for this month
        adhoc = 0
        if month in config.adhoc_payments:
            adhoc = min(config.adhoc_payments[month], balance - base_principal - extra - q_pay)
            if adhoc < 0:
                adhoc = 0

        # Total principal reduction this month
        total_principal = base_principal + extra + q_pay + adhoc
        if total_principal > balance:
            total_principal = balance
            # Adjust components proportionally
            overshoot = (base_principal + extra + q_pay + adhoc) - balance
            if adhoc > 0:
                adhoc = max(0, adhoc - overshoot)
                overshoot -= min(overshoot, adhoc)
            if q_pay > 0 and overshoot > 0:
                q_pay = max(0, q_pay - overshoot)
                overshoot -= min(overshoot, q_pay)
            if extra > 0 and overshoot > 0:
                extra = max(0, extra - overshoot)

        balance = max(0, balance - total_principal)
        total_interest += interest
        actual_payment = interest + total_principal
        total_paid += actual_payment
        total_extra += extra + q_pay
        total_adhoc += adhoc

        schedule.append(MonthDetail(
            month=month,
            payment=actual_payment,
            principal_paid=base_principal,
            interest_paid=interest,
            extra_paid=extra + q_pay,
            adhoc_paid=adhoc,
            balance=balance,
            cumulative_interest=total_interest,
            cumulative_paid=total_paid + config.initial_lump_sum,
            current_emi=base_payment,
        ))

        # RE-AMORTIZE: After ANY extra payment (quarterly, erratic, or monthly extra)
        # reduces balance AND recalculates EMI on the lower principal
        # UNLESS fixed_emi mode (car loans) — EMI stays the same, loan just ends sooner
        if not config.fixed_emi:
            had_extra = (extra + q_pay + adhoc) > 0.01
            if had_extra and balance > 0.01:
                remaining_months = n - month
                if remaining_months > 0:
                    base_payment = balance * (r * (1 + r) ** remaining_months) / ((1 + r) ** remaining_months - 1)

        if balance <= 0.01:
            break

    return LoanResult(
        monthly_payment=initial_payment,
        current_emi=base_payment,  # final EMI at end of loan
        total_interest=total_interest,
        total_paid=total_paid + config.initial_lump_sum,
        total_months=month,
        schedule=schedule,
        total_extra_paid=total_extra,
        total_adhoc_paid=total_adhoc,
    )


def format_time(months: int) -> str:
    """Format months as 'Xy Zm'."""
    y = months // 12
    m = months % 12
    if y == 0:
        return f"{m}m"
    if m == 0:
        return f"{y}y"
    return f"{y}y {m}m"


# ─────────────────────────────────────────────
# STREAMLIT PAGE CONFIG
# ─────────────────────────────────────────────

st.set_page_config(
    page_title="Loan Payoff Optimizer",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&display=swap');
    
    .stApp { background-color: #0f1419; }
    
    .main-header {
        background: linear-gradient(135deg, #1a1f2e 0%, #0f1419 100%);
        border: 1px solid #2a3040;
        border-radius: 16px;
        padding: 24px 32px;
        margin-bottom: 24px;
    }
    .main-header h1 {
        color: #e2e8f0;
        font-size: 28px;
        margin: 0;
    }
    .main-header p {
        color: #64748b;
        font-size: 14px;
        margin: 4px 0 0 0;
    }
    .main-header .tag {
        color: #fb7185;
        font-size: 11px;
        letter-spacing: 2px;
        text-transform: uppercase;
    }
    
    .metric-card {
        background: #111827;
        border: 1px solid #1e293b;
        border-radius: 12px;
        padding: 16px 20px;
        position: relative;
        overflow: hidden;
    }
    .metric-card .bar {
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 3px;
    }
    .metric-card .label {
        font-size: 11px;
        color: #94a3b8;
        letter-spacing: 0.5px;
        margin-bottom: 4px;
    }
    .metric-card .value {
        font-size: 24px;
        font-weight: 700;
        font-family: 'JetBrains Mono', monospace;
    }
    .metric-card .sub {
        font-size: 11px;
        color: #64748b;
        margin-top: 4px;
    }
    
    .insight-box {
        border-radius: 12px;
        padding: 16px 20px;
        margin: 12px 0;
    }
    .insight-box.green {
        background: rgba(52,211,153,0.08);
        border: 1px solid rgba(52,211,153,0.25);
    }
    .insight-box.amber {
        background: rgba(251,191,36,0.08);
        border: 1px solid rgba(251,191,36,0.25);
    }
    .insight-box.rose {
        background: rgba(251,113,133,0.08);
        border: 1px solid rgba(251,113,133,0.25);
    }
    .insight-box.teal {
        background: rgba(45,212,191,0.08);
        border: 1px solid rgba(45,212,191,0.25);
    }
    
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background: #111827;
    }
    
    /* Metric override */
    [data-testid="stMetricValue"] {
        font-family: 'JetBrains Mono', monospace;
    }
    
    div[data-testid="stExpander"] {
        background: #111827;
        border: 1px solid #1e293b;
        border-radius: 12px;
    }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# SIDEBAR — LOAN INPUTS
# ─────────────────────────────────────────────

with st.sidebar:
    st.markdown("### 🏦 Loan Details")
    
    principal = st.number_input(
        "Loan Amount ($)",
        min_value=1000, max_value=1_000_000,
        value=60000, step=1000,
        help="Total loan principal"
    )
    
    rate = st.slider(
        "Annual Interest Rate (%)",
        min_value=1.0, max_value=30.0,
        value=13.0, step=0.25,
        help="Annual percentage rate"
    )
    
    term = st.slider(
        "Loan Term (years)",
        min_value=1, max_value=30,
        value=15, step=1,
        help="Original loan tenure"
    )
    
    from datetime import date, timedelta
    loan_start_date = st.date_input(
        "Loan Start Date",
        value=date.today(),
        help="When your loan started (or will start). Used to calculate which payments have already happened.",
    )
    
    emi_as_of_date = st.date_input(
        "View EMI as of",
        value=date.today(),
        min_value=loan_start_date,
        help="See your EMI as of this date. Only payments before this date "
             "will be counted for the Current EMI calculation.",
    )
    
    # Calculate months elapsed
    months_elapsed = (emi_as_of_date.year - loan_start_date.year) * 12 + (emi_as_of_date.month - loan_start_date.month)
    months_elapsed = max(0, months_elapsed)
    
    st.markdown("---")
    st.markdown("### ⚙️ Loan Type")
    fixed_emi = st.toggle(
        "Fixed EMI (car loan style)",
        value=False,
        help="ON = payment stays fixed, extra payments make the loan end sooner. "
             "OFF = payment recalculates lower after extra payments, tenure stays the same. "
             "Most student loans recalculate. Most car loans are fixed.",
    )
    
    st.markdown("---")
    st.markdown("### 💸 Early Payment Options")
    
    initial_lump = st.number_input(
        "Initial Lump Sum ($)",
        min_value=0, max_value=int(principal),
        value=0, step=1000,
        help="One-time payment made upfront to reduce principal"
    )
    
    quarterly = st.number_input(
        "Quarterly Extra Payment ($)",
        min_value=0, max_value=50000,
        value=0, step=500,
        help="Extra payment made every 3 months toward principal"
    )
    
    extra_monthly = st.number_input(
        "Extra Monthly Payment ($)",
        min_value=0, max_value=5000,
        value=0, step=25,
        help="Additional amount added to each monthly payment"
    )
    
    st.markdown("---")
    st.markdown("### 🎯 Ad-Hoc / Erratic Payments")
    st.caption("Add one-time payments at specific months")
    
    # Initialize session state for adhoc payments
    if "adhoc_payments" not in st.session_state:
        st.session_state.adhoc_payments = {}
    
    # Add new adhoc payment
    with st.expander("➕ Add an erratic payment", expanded=False):
        col_m, col_a = st.columns(2)
        with col_m:
            adhoc_month = st.number_input(
                "At month #",
                min_value=1, max_value=term * 12,
                value=6, step=1,
                key="adhoc_month_input"
            )
        with col_a:
            adhoc_amount = st.number_input(
                "Amount ($)",
                min_value=100, max_value=50000,
                value=2000, step=100,
                key="adhoc_amount_input"
            )
        
        if st.button("Add Payment", type="primary", use_container_width=True):
            st.session_state.adhoc_payments[adhoc_month] = (
                st.session_state.adhoc_payments.get(adhoc_month, 0) + adhoc_amount
            )
            st.rerun()
    
    # Display existing adhoc payments
    if st.session_state.adhoc_payments:
        st.markdown("**Scheduled erratic payments:**")
        payments_to_remove = []
        for m in sorted(st.session_state.adhoc_payments.keys()):
            amt = st.session_state.adhoc_payments[m]
            col_info, col_del = st.columns([3, 1])
            with col_info:
                yr = m // 12
                mo = m % 12
                st.markdown(f"Month {m} ({yr}y {mo}m): **${amt:,.0f}**")
            with col_del:
                if st.button("✕", key=f"del_{m}"):
                    payments_to_remove.append(m)
        
        for m in payments_to_remove:
            del st.session_state.adhoc_payments[m]
            st.rerun()
        
        if st.button("Clear All Erratic Payments", use_container_width=True):
            st.session_state.adhoc_payments = {}
            st.rerun()
    else:
        st.caption("No erratic payments added yet")


# ─────────────────────────────────────────────
# CALCULATIONS
# ─────────────────────────────────────────────

# Original loan (no extras)
original = calculate_loan(LoanConfig(
    principal=principal,
    annual_rate=rate,
    term_years=term,
    fixed_emi=fixed_emi,
))

# With all extras
optimized = calculate_loan(LoanConfig(
    principal=principal,
    annual_rate=rate,
    term_years=term,
    initial_lump_sum=initial_lump,
    extra_monthly=extra_monthly,
    quarterly_payment=quarterly,
    adhoc_payments=st.session_state.adhoc_payments,
    fixed_emi=fixed_emi,
))

# Lump sum only
lump_only = calculate_loan(LoanConfig(
    principal=principal,
    annual_rate=rate,
    term_years=term,
    initial_lump_sum=initial_lump,
    fixed_emi=fixed_emi,
))

interest_saved = original.total_interest - optimized.total_interest
time_saved = original.total_months - optimized.total_months


# ─────────────────────────────────────────────
# MAIN CONTENT
# ─────────────────────────────────────────────

# Header
st.markdown(f"""
<div class="main-header">
    <div class="tag">Financial Lab</div>
    <h1>💰 Loan Payoff Optimizer</h1>
    <p>${principal:,.0f} @ {rate}% for {term} years • 
    Interactive calculator with lump sum, quarterly, monthly & erratic payment modeling</p>
</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# TAB LAYOUT
# ─────────────────────────────────────────────

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Dashboard",
    "📅 Payoff Timeline",
    "🎯 Erratic Payments Impact",
    "📋 Amortization Schedule",
    "🔬 Scenario Lab",
])


# ═══════════════ TAB 1: DASHBOARD ═══════════════
with tab1:
    
    # Key Metrics Row
    c1, c2, c3, c4, c5 = st.columns(5)
    
    with c1:
        st.metric(
            "Original Payoff",
            format_time(original.total_months),
            f"EMI: ${original.monthly_payment:,.0f}/mo",
        )
    with c2:
        st.metric(
            "🚀 New Payoff",
            format_time(optimized.total_months),
            f"-{format_time(time_saved)} faster",
            delta_color="inverse",
        )
    with c3:
        st.metric(
            "💰 Interest Saved",
            f"${interest_saved:,.0f}",
            f"-{interest_saved/original.total_interest*100:.0f}% interest" if original.total_interest > 0 else "",
            delta_color="inverse",
        )
    with c4:
        starting_emi = optimized.monthly_payment
        st.metric(
            "Starting EMI",
            f"${starting_emi:,.0f}",
            f"${starting_emi - original.monthly_payment:+,.0f} vs original",
            delta_color="inverse",
            help="Your monthly payment at loan start (after initial lump sum). "
                 "Before any quarterly or erratic payments kick in.",
        )
    with c5:
        if fixed_emi:
            # Fixed EMI mode: payment never changes
            current_emi = starting_emi
            emi_reduction = current_emi - original.monthly_payment
            as_of_label = emi_as_of_date.strftime("%b %Y")
            st.metric(
                "🔒 Fixed EMI",
                f"${current_emi:,.0f}",
                f"${emi_reduction:+,.0f} vs original",
                delta_color="inverse",
                help="Fixed EMI mode (car loan style). Your payment never changes — "
                     "extra payments make the loan end sooner instead of reducing your EMI.",
            )
        else:
            # Recalculated EMI mode: find EMI at months_elapsed
            display_emi = optimized.monthly_payment  # default: starting EMI
            if optimized.schedule:
                if months_elapsed <= 0:
                    display_emi = optimized.monthly_payment
                elif months_elapsed >= len(optimized.schedule):
                    display_emi = optimized.schedule[-1].current_emi
                else:
                    for s in optimized.schedule:
                        if s.month <= months_elapsed:
                            display_emi = s.current_emi
                        else:
                            break
            
            current_emi = display_emi
            emi_reduction = current_emi - original.monthly_payment
            
            as_of_label = emi_as_of_date.strftime("%b %Y")
            st.metric(
                f"📉 EMI as of {as_of_label}",
                f"${current_emi:,.0f}",
                f"${emi_reduction:+,.0f} vs original",
                delta_color="inverse",
                help=f"Your EMI as of {as_of_label} ({months_elapsed} months into the loan). "
                     "All payments (lump sum, quarterly, erratic) that have happened by this "
                     "date reduce the principal and recalculate your EMI. Move the date forward "
                     "to see your future EMI.",
            )
    
    # Show EMI journey or fixed EMI explanation
    has_extras = quarterly > 0 or st.session_state.adhoc_payments or extra_monthly > 0
    
    if fixed_emi and has_extras:
        st.markdown(f"""
<div class="insight-box amber">
    <strong style="color: #fbbf24;">🔒 Fixed EMI Mode — Your Payment Stays at ${starting_emi:,.0f}/mo</strong><br>
    <span style="color: #94a3b8; font-size: 13px;">
    In fixed EMI mode (car loans), extra payments reduce your balance but your monthly 
    payment stays the same. The benefit? Your loan ends in 
    <strong>{format_time(optimized.total_months)}</strong> instead of 
    <strong>{format_time(original.total_months)}</strong> — 
    <strong>{format_time(time_saved)} sooner</strong>. 
    Toggle off "Fixed EMI" in the sidebar to see how the same payments would lower 
    your monthly EMI instead.
    </span>
</div>
""", unsafe_allow_html=True)
    
    elif not fixed_emi:
        emi_dropped = abs(current_emi - starting_emi) > 1
        if has_extras and emi_dropped:
            emi_changes = []
            prev_emi = None
            for s in optimized.schedule:
                emi_val = round(s.current_emi, 2)
                if prev_emi is None or abs(emi_val - prev_emi) > 0.50:
                    emi_changes.append((s.month, emi_val))
                    prev_emi = emi_val
            
            if len(emi_changes) > 1:
                as_of_label = emi_as_of_date.strftime("%b %Y")
                st.markdown(f"""
<div class="insight-box green">
    <strong style="color: #34d399;">📉 Your EMI Drops With Each Extra Payment</strong><br>
    <span style="color: #94a3b8; font-size: 13px;">
    Every extra payment (lump sum, quarterly, erratic) reduces your principal and 
    recalculates the EMI. As of <strong>{as_of_label}</strong> (month {months_elapsed}), 
    your EMI is <strong>${current_emi:,.0f}</strong> — down from 
    <strong>${starting_emi:,.0f}</strong>. 
    Move the "View EMI as of" date in the sidebar to see how it changes over time.
    </span>
</div>
""", unsafe_allow_html=True)
                
                fig_emi = go.Figure()
                fig_emi.add_trace(go.Scatter(
                    x=[e[0] for e in emi_changes], y=[e[1] for e in emi_changes],
                    mode="lines+markers", name="EMI Over Time",
                    line=dict(color="#34d399", width=3, shape="hv"),
                    marker=dict(size=8, color="#34d399"),
                    fill="tozeroy", fillcolor="rgba(52,211,153,0.08)",
                ))
                fig_emi.add_hline(
                    y=original.monthly_payment, line_dash="dash",
                    line_color="#fb7185", opacity=0.5,
                    annotation_text=f"Original EMI: ${original.monthly_payment:,.0f}",
                    annotation_position="top right",
                )
                # Mark the "as of" position
                if months_elapsed > 0 and months_elapsed < optimized.total_months:
                    fig_emi.add_vline(
                        x=months_elapsed, line_dash="dot",
                        line_color="#22d3ee", opacity=0.7,
                        annotation_text=f"Today ({as_of_label})",
                        annotation_position="top left",
                        annotation_font_color="#22d3ee",
                    )
                fig_emi.update_layout(
                    title="EMI Step-Down Schedule",
                    xaxis_title="Month", yaxis_title="Monthly EMI ($)",
                    height=300, template="plotly_dark",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(17,24,39,0.5)",
                    font_color="#94a3b8",
                    yaxis=dict(gridcolor="rgba(30,41,59,0.5)", tickprefix="$"),
                    xaxis=dict(gridcolor="rgba(30,41,59,0.5)"),
                    margin=dict(t=40, b=40),
                )
                st.plotly_chart(fig_emi, use_container_width=True)
    
    st.markdown("")
    
    # Comparison Table
    col_left, col_right = st.columns([1.2, 1])
    
    with col_left:
        st.markdown("#### Before vs After")
        
        emi_row_label = "Fixed EMI" if fixed_emi else f"EMI as of {as_of_label}"
        
        comparison_data = {
            "Metric": [
                "Starting EMI",
                emi_row_label,
                "Total Interest",
                "Total Amount Paid",
                "Payoff Time",
                "Extra Payments Made",
            ],
            "Original": [
                f"${original.monthly_payment:,.0f}",
                f"${original.monthly_payment:,.0f}",
                f"${original.total_interest:,.0f}",
                f"${original.total_paid:,.0f}",
                format_time(original.total_months),
                "$0",
            ],
            "Your Plan": [
                f"${optimized.monthly_payment:,.0f}",
                f"${current_emi:,.0f}",
                f"${optimized.total_interest:,.0f}",
                f"${optimized.total_paid:,.0f}",
                format_time(optimized.total_months),
                f"${initial_lump + optimized.total_extra_paid + optimized.total_adhoc_paid:,.0f}",
            ],
            "Savings": [
                f"${original.monthly_payment - optimized.monthly_payment:,.0f}/mo"
                if initial_lump > 0 else "—",
                f"${original.monthly_payment - current_emi:,.0f}/mo saved",
                f"${interest_saved:,.0f}",
                f"${original.total_paid - optimized.total_paid:,.0f}",
                f"{format_time(time_saved)} faster",
                "—",
            ],
        }
        
        df_compare = pd.DataFrame(comparison_data)
        st.dataframe(
            df_compare,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Metric": st.column_config.TextColumn(width="medium"),
                "Original": st.column_config.TextColumn(width="small"),
                "Your Plan": st.column_config.TextColumn(width="small"),
                "Savings": st.column_config.TextColumn(width="small"),
            },
        )
    
    with col_right:
        st.markdown("#### Payment Breakdown")
        
        # Donut chart of where money goes
        labels = ["Interest (Original)", "Interest (Your Plan)", "Interest Eliminated"]
        values = [optimized.total_interest, interest_saved, 0]
        
        fig_donut = go.Figure(data=[go.Pie(
            labels=["Interest You Pay", "Interest Saved", "Principal"],
            values=[optimized.total_interest, interest_saved, principal],
            hole=0.55,
            marker_colors=["#fb7185", "#34d399", "#22d3ee"],
            textinfo="label+percent",
            textfont_size=11,
        )])
        fig_donut.update_layout(
            showlegend=False,
            height=300,
            margin=dict(t=20, b=20, l=20, r=20),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_color="#94a3b8",
        )
        st.plotly_chart(fig_donut, use_container_width=True)
    
    # Balance Over Time Chart
    st.markdown("#### 📉 Balance Over Time")
    
    months_orig = [s.month for s in original.schedule]
    balance_orig = [s.balance for s in original.schedule]
    months_opt = [s.month for s in optimized.schedule]
    balance_opt = [s.balance for s in optimized.schedule]
    
    fig_balance = go.Figure()
    fig_balance.add_trace(go.Scatter(
        x=months_orig, y=balance_orig,
        mode="lines", name="Original Plan",
        line=dict(color="#fb7185", width=2, dash="dash"),
        fill="tozeroy",
        fillcolor="rgba(251,113,133,0.08)",
    ))
    fig_balance.add_trace(go.Scatter(
        x=months_opt, y=balance_opt,
        mode="lines", name="Your Optimized Plan",
        line=dict(color="#2dd4bf", width=3),
        fill="tozeroy",
        fillcolor="rgba(45,212,191,0.1)",
    ))
    
    # Mark adhoc payments on chart
    if st.session_state.adhoc_payments:
        adhoc_months = []
        adhoc_balances = []
        adhoc_texts = []
        for s in optimized.schedule:
            if s.month in st.session_state.adhoc_payments and s.adhoc_paid > 0:
                adhoc_months.append(s.month)
                adhoc_balances.append(s.balance)
                adhoc_texts.append(f"${s.adhoc_paid:,.0f} payment")
        
        if adhoc_months:
            fig_balance.add_trace(go.Scatter(
                x=adhoc_months, y=adhoc_balances,
                mode="markers+text",
                name="Erratic Payments",
                marker=dict(color="#fbbf24", size=12, symbol="star"),
                text=adhoc_texts,
                textposition="top center",
                textfont=dict(size=10, color="#fbbf24"),
            ))
    
    fig_balance.update_layout(
        xaxis_title="Month",
        yaxis_title="Remaining Balance ($)",
        height=400,
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(17,24,39,0.5)",
        font_color="#94a3b8",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        xaxis=dict(gridcolor="rgba(30,41,59,0.5)"),
        yaxis=dict(gridcolor="rgba(30,41,59,0.5)", tickprefix="$"),
    )
    st.plotly_chart(fig_balance, use_container_width=True)
    
    # Insight box
    if interest_saved > 0:
        st.markdown(f"""
<div class="insight-box green">
    <strong style="color: #34d399;">💡 The Math Behind Your Savings</strong><br>
    <span style="color: #94a3b8; font-size: 13px;">
    Every $1 you prepay on a {rate}% loan saves you ${rate/100:.2f} in interest per year.
    Your total extra payments of <strong>${initial_lump + optimized.total_extra_paid + optimized.total_adhoc_paid:,.0f}</strong> 
    eliminate <strong>${interest_saved:,.0f}</strong> in interest — 
    that's a <strong>{interest_saved/(initial_lump + optimized.total_extra_paid + optimized.total_adhoc_paid)*100:.0f}% return</strong> 
    on your extra payments. No stock market investment gives you a guaranteed {rate}% return.
    </span>
</div>
""", unsafe_allow_html=True)


# ═══════════════ TAB 2: PAYOFF TIMELINE ═══════════════
with tab2:
    st.markdown("#### ⏱️ How Each Strategy Layers Up")
    st.caption("See how each payment type accelerates your payoff independently and combined")
    
    # Calculate each layer
    configs = [
        ("Original (no extras)", LoanConfig(principal=principal, annual_rate=rate, term_years=term, fixed_emi=fixed_emi)),
        (f"+ ${initial_lump:,.0f} lump sum", LoanConfig(principal=principal, annual_rate=rate, term_years=term, initial_lump_sum=initial_lump, fixed_emi=fixed_emi)),
        (f"+ ${extra_monthly:,.0f}/mo extra", LoanConfig(principal=principal, annual_rate=rate, term_years=term, initial_lump_sum=initial_lump, extra_monthly=extra_monthly, fixed_emi=fixed_emi)),
        (f"+ ${quarterly:,.0f}/quarter", LoanConfig(principal=principal, annual_rate=rate, term_years=term, initial_lump_sum=initial_lump, extra_monthly=extra_monthly, quarterly_payment=quarterly, fixed_emi=fixed_emi)),
        ("+ Erratic payments", LoanConfig(principal=principal, annual_rate=rate, term_years=term, initial_lump_sum=initial_lump, extra_monthly=extra_monthly, quarterly_payment=quarterly, adhoc_payments=st.session_state.adhoc_payments, fixed_emi=fixed_emi)),
    ]
    
    colors = ["#fb7185", "#fbbf24", "#a78bfa", "#34d399", "#22d3ee"]
    
    results = [(name, calculate_loan(cfg)) for name, cfg in configs]
    
    # Layered line chart
    fig_layers = go.Figure()
    for i, (name, result) in enumerate(results):
        months = [s.month for s in result.schedule]
        balances = [s.balance for s in result.schedule]
        fig_layers.add_trace(go.Scatter(
            x=months, y=balances,
            mode="lines", name=name,
            line=dict(
                color=colors[i],
                width=3 if i == len(results) - 1 else 1.5,
                dash="dash" if i == 0 else None,
            ),
        ))
    
    fig_layers.update_layout(
        xaxis_title="Month",
        yaxis_title="Balance ($)",
        height=450,
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(17,24,39,0.5)",
        font_color="#94a3b8",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        yaxis=dict(gridcolor="rgba(30,41,59,0.5)", tickprefix="$"),
        xaxis=dict(gridcolor="rgba(30,41,59,0.5)"),
    )
    st.plotly_chart(fig_layers, use_container_width=True)
    
    # Summary table for each layer
    st.markdown("#### Impact of Each Layer")
    
    layer_data = []
    for i, (name, result) in enumerate(results):
        saved_vs_original = original.total_interest - result.total_interest
        time_vs_original = original.total_months - result.total_months
        layer_data.append({
            "Strategy": name,
            "Payoff Time": format_time(result.total_months),
            "Monthly EMI": f"${result.monthly_payment:,.0f}",
            "Total Interest": f"${result.total_interest:,.0f}",
            "Interest Saved": f"${saved_vs_original:,.0f}" if saved_vs_original > 0 else "—",
            "Time Saved": format_time(time_vs_original) if time_vs_original > 0 else "—",
        })
    
    st.dataframe(pd.DataFrame(layer_data), use_container_width=True, hide_index=True)
    
    # Horizontal bar chart for payoff time
    st.markdown("#### Payoff Time Comparison")
    
    fig_bar = go.Figure()
    for i, (name, result) in enumerate(reversed(results)):
        fig_bar.add_trace(go.Bar(
            y=[name], x=[result.total_months],
            orientation="h",
            name=name,
            marker_color=colors[len(results) - 1 - i],
            text=f"{format_time(result.total_months)}",
            textposition="inside",
            textfont=dict(size=12, color="white"),
            showlegend=False,
        ))
    
    fig_bar.update_layout(
        height=300,
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(17,24,39,0.5)",
        font_color="#94a3b8",
        xaxis_title="Months to Payoff",
        barmode="group",
        xaxis=dict(gridcolor="rgba(30,41,59,0.5)"),
        yaxis=dict(gridcolor="rgba(30,41,59,0.5)"),
    )
    st.plotly_chart(fig_bar, use_container_width=True)


# ═══════════════ TAB 3: ERRATIC PAYMENTS ═══════════════
with tab3:
    st.markdown("#### 🎯 Ad-Hoc / Erratic Payment Impact Analysis")
    st.caption("See exactly how one-time payments at specific months change your loan trajectory")
    
    if not st.session_state.adhoc_payments:
        st.info(
            "👈 **Add erratic payments in the sidebar** to see their impact here.\n\n"
            "An erratic payment is a one-time extra payment at a specific month — "
            "like a $2,000 bonus you put toward the loan at month 6, or a $5,000 tax refund at month 12."
        )
        
        st.markdown("#### 🧪 Quick Scenario: What if you dropped $2K at month 6?")
        
        # Show a demo comparison
        demo_adhoc = {6: 2000}
        without_adhoc = calculate_loan(LoanConfig(
            principal=principal, annual_rate=rate, term_years=term,
            initial_lump_sum=initial_lump, extra_monthly=extra_monthly,
            quarterly_payment=quarterly, fixed_emi=fixed_emi,
        ))
        with_adhoc = calculate_loan(LoanConfig(
            principal=principal, annual_rate=rate, term_years=term,
            initial_lump_sum=initial_lump, extra_monthly=extra_monthly,
            quarterly_payment=quarterly, adhoc_payments=demo_adhoc, fixed_emi=fixed_emi,
        ))
        
        demo_saved = without_adhoc.total_interest - with_adhoc.total_interest
        demo_time = without_adhoc.total_months - with_adhoc.total_months
        
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Interest Saved", f"${demo_saved:,.0f}", "from just $2K")
        with c2:
            st.metric("Time Saved", format_time(demo_time), "months earlier")
        with c3:
            st.metric("ROI on $2K", f"{demo_saved/2000*100:.0f}%", "guaranteed return")
        
        st.markdown(f"""
<div class="insight-box amber">
    <strong style="color: #fbbf24;">💡 A single $2,000 payment at month 6 saves you ${demo_saved:,.0f} in interest.</strong><br>
    <span style="color: #94a3b8; font-size: 13px;">
    That's a {demo_saved/2000*100:.0f}% return on your money — guaranteed, risk-free. 
    Add this payment in the sidebar to include it in your plan.
    </span>
</div>
""", unsafe_allow_html=True)
    
    else:
        # With vs without adhoc comparison
        without_adhoc = calculate_loan(LoanConfig(
            principal=principal, annual_rate=rate, term_years=term,
            initial_lump_sum=initial_lump, extra_monthly=extra_monthly,
            quarterly_payment=quarterly, fixed_emi=fixed_emi,
        ))
        
        adhoc_interest_saved = without_adhoc.total_interest - optimized.total_interest
        adhoc_time_saved = without_adhoc.total_months - optimized.total_months
        total_adhoc_amount = sum(st.session_state.adhoc_payments.values())
        
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Total Erratic Payments", f"${total_adhoc_amount:,.0f}",
                      f"{len(st.session_state.adhoc_payments)} payment(s)")
        with c2:
            st.metric("Additional Interest Saved", f"${adhoc_interest_saved:,.0f}",
                      "beyond regular extras")
        with c3:
            st.metric("Additional Time Saved", format_time(adhoc_time_saved),
                      "beyond regular extras")
        with c4:
            roi = (adhoc_interest_saved / total_adhoc_amount * 100) if total_adhoc_amount > 0 else 0
            st.metric("ROI on Erratic Payments", f"{roi:.0f}%", "guaranteed return")
        
        st.markdown("")
        
        # Individual payment impact
        st.markdown("#### Impact of Each Erratic Payment")
        
        impact_data = []
        for month_num in sorted(st.session_state.adhoc_payments.keys()):
            amt = st.session_state.adhoc_payments[month_num]
            
            # Calculate with just this one adhoc payment
            single_adhoc = calculate_loan(LoanConfig(
                principal=principal, annual_rate=rate, term_years=term,
                initial_lump_sum=initial_lump, extra_monthly=extra_monthly,
                quarterly_payment=quarterly, adhoc_payments={month_num: amt},
                fixed_emi=fixed_emi,
            ))
            
            saved = without_adhoc.total_interest - single_adhoc.total_interest
            time_diff = without_adhoc.total_months - single_adhoc.total_months
            
            impact_data.append({
                "Month": month_num,
                "When": f"Month {month_num} ({month_num // 12}y {month_num % 12}m)",
                "Amount": f"${amt:,.0f}",
                "Interest Saved": f"${saved:,.0f}",
                "Time Saved": format_time(time_diff) if time_diff > 0 else "< 1 month",
                "ROI": f"{saved/amt*100:.0f}%",
            })
        
        df_impact = pd.DataFrame(impact_data)
        st.dataframe(df_impact.drop(columns=["Month"]), use_container_width=True, hide_index=True)
        
        st.markdown(f"""
<div class="insight-box teal">
    <strong style="color: #2dd4bf;">💡 Earlier payments save more.</strong><br>
    <span style="color: #94a3b8; font-size: 13px;">
    A payment at month 6 saves more interest than the same payment at month 36, 
    because the earlier payment has more time to reduce the compounding interest. 
    Whenever you get a bonus, tax refund, or windfall — throw it at the loan immediately.
    </span>
</div>
""", unsafe_allow_html=True)
        
        # Chart: with vs without adhoc
        st.markdown("#### Balance: With vs Without Erratic Payments")
        
        fig_adhoc = go.Figure()
        fig_adhoc.add_trace(go.Scatter(
            x=[s.month for s in without_adhoc.schedule],
            y=[s.balance for s in without_adhoc.schedule],
            mode="lines", name="Without erratic payments",
            line=dict(color="#a78bfa", width=2, dash="dash"),
        ))
        fig_adhoc.add_trace(go.Scatter(
            x=[s.month for s in optimized.schedule],
            y=[s.balance for s in optimized.schedule],
            mode="lines", name="With erratic payments",
            line=dict(color="#22d3ee", width=3),
        ))
        
        # Mark payment points
        for s in optimized.schedule:
            if s.month in st.session_state.adhoc_payments and s.adhoc_paid > 0:
                fig_adhoc.add_trace(go.Scatter(
                    x=[s.month], y=[s.balance],
                    mode="markers+text",
                    marker=dict(color="#fbbf24", size=14, symbol="star"),
                    text=[f"${s.adhoc_paid:,.0f}"],
                    textposition="top center",
                    textfont=dict(color="#fbbf24", size=11),
                    showlegend=False,
                ))
        
        fig_adhoc.update_layout(
            height=400,
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(17,24,39,0.5)",
            font_color="#94a3b8",
            xaxis_title="Month",
            yaxis_title="Balance ($)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            yaxis=dict(gridcolor="rgba(30,41,59,0.5)", tickprefix="$"),
            xaxis=dict(gridcolor="rgba(30,41,59,0.5)"),
        )
        st.plotly_chart(fig_adhoc, use_container_width=True)


# ═══════════════ TAB 4: AMORTIZATION SCHEDULE ═══════════════
with tab4:
    st.markdown("#### 📋 Full Amortization Schedule")
    st.caption("Month-by-month breakdown of your optimized loan")
    
    # Toggle view
    view_mode = st.radio(
        "Show schedule for:",
        ["Optimized Plan (with all extras)", "Original Plan (no extras)"],
        horizontal=True,
    )
    
    schedule = optimized.schedule if "Optimized" in view_mode else original.schedule
    
    schedule_data = []
    for s in schedule:
        row = {
            "Month": s.month,
            "Year": f"Y{s.month // 12}.{s.month % 12:02d}",
            "EMI": round(s.current_emi, 2),
            "Payment": round(s.payment, 2),
            "Principal": round(s.principal_paid, 2),
            "Interest": round(s.interest_paid, 2),
            "Extra": round(s.extra_paid, 2),
            "Balance": round(s.balance, 2),
            "Cumulative Interest": round(s.cumulative_interest, 2),
        }
        if "Optimized" in view_mode:
            row["Ad-Hoc"] = round(s.adhoc_paid, 2)
        schedule_data.append(row)
    
    df_schedule = pd.DataFrame(schedule_data)
    
    # Format columns
    money_cols = ["EMI", "Payment", "Principal", "Interest", "Extra", "Balance", "Cumulative Interest"]
    if "Ad-Hoc" in df_schedule.columns:
        money_cols.append("Ad-Hoc")
    
    col_config = {}
    for col in money_cols:
        col_config[col] = st.column_config.NumberColumn(format="$%.2f")
    
    st.dataframe(df_schedule, use_container_width=True, hide_index=True, column_config=col_config, height=500)
    
    # Interest vs Principal over time
    st.markdown("#### Interest vs Principal Split Over Time")
    
    fig_split = make_subplots(specs=[[{"secondary_y": False}]])
    
    months = [s.month for s in schedule]
    interest_payments = [s.interest_paid for s in schedule]
    principal_payments = [s.principal_paid + s.extra_paid + s.adhoc_paid for s in schedule]
    
    fig_split.add_trace(go.Bar(
        x=months, y=interest_payments,
        name="Interest",
        marker_color="#fb7185",
    ))
    fig_split.add_trace(go.Bar(
        x=months, y=principal_payments,
        name="Principal + Extras",
        marker_color="#34d399",
    ))
    
    fig_split.update_layout(
        barmode="stack",
        height=400,
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(17,24,39,0.5)",
        font_color="#94a3b8",
        xaxis_title="Month",
        yaxis_title="Payment Amount ($)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        yaxis=dict(gridcolor="rgba(30,41,59,0.5)", tickprefix="$"),
        xaxis=dict(gridcolor="rgba(30,41,59,0.5)"),
    )
    st.plotly_chart(fig_split, use_container_width=True)
    
    st.markdown(f"""
<div class="insight-box amber">
    <strong style="color: #fbbf24;">💡 Notice the crossover point.</strong><br>
    <span style="color: #94a3b8; font-size: 13px;">
    In the early months, most of your payment goes to interest (red). As you pay down the balance, 
    more goes to principal (green). Extra payments accelerate this crossover — that's why early 
    prepayments are so powerful.
    </span>
</div>
""", unsafe_allow_html=True)
    
    # Download button
    csv = df_schedule.to_csv(index=False)
    st.download_button(
        label="📥 Download Amortization Schedule (CSV)",
        data=csv,
        file_name="amortization_schedule.csv",
        mime="text/csv",
        use_container_width=True,
    )


# ═══════════════ TAB 5: SCENARIO LAB ═══════════════
with tab5:
    st.markdown("#### 🔬 Scenario Lab — Test Different Strategies")
    st.caption("Compare quarterly payment amounts side by side")
    
    # Quarterly scenarios
    quarterly_amounts = [0, 1000, 2000, 3000, 5000, 7500, 10000]
    
    scenario_data = []
    for q in quarterly_amounts:
        result = calculate_loan(LoanConfig(
            principal=principal, annual_rate=rate, term_years=term,
            initial_lump_sum=initial_lump, extra_monthly=extra_monthly,
            quarterly_payment=q, adhoc_payments=st.session_state.adhoc_payments,
            fixed_emi=fixed_emi,
        ))
        
        saved = original.total_interest - result.total_interest
        time_diff = original.total_months - result.total_months
        
        scenario_data.append({
            "Quarterly": f"${q:,.0f}",
            "Per Year": f"${q * 4:,.0f}",
            "Payoff Time": format_time(result.total_months),
            "Time Saved": format_time(time_diff) if time_diff > 0 else "—",
            "Total Interest": f"${result.total_interest:,.0f}",
            "Interest Saved": f"${saved:,.0f}" if saved > 0 else "—",
            "Monthly EMI": f"${result.monthly_payment:,.0f}",
            "_months": result.total_months,
            "_saved": saved,
        })
    
    df_scenarios = pd.DataFrame(scenario_data)
    display_cols = [c for c in df_scenarios.columns if not c.startswith("_")]
    st.dataframe(df_scenarios[display_cols], use_container_width=True, hide_index=True)
    
    # Visual comparison
    fig_scenarios = go.Figure()
    
    fig_scenarios.add_trace(go.Bar(
        x=[s["Quarterly"] for s in scenario_data],
        y=[s["_months"] for s in scenario_data],
        name="Payoff Time (months)",
        marker_color=[
            "#22d3ee" if s["Quarterly"] == f"${quarterly:,.0f}" else "#1e293b"
            for s in scenario_data
        ],
        text=[format_time(s["_months"]) for s in scenario_data],
        textposition="outside",
        textfont=dict(size=11),
    ))
    
    fig_scenarios.update_layout(
        height=400,
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(17,24,39,0.5)",
        font_color="#94a3b8",
        xaxis_title="Quarterly Payment Amount",
        yaxis_title="Months to Payoff",
        yaxis=dict(gridcolor="rgba(30,41,59,0.5)"),
        xaxis=dict(gridcolor="rgba(30,41,59,0.5)"),
    )
    st.plotly_chart(fig_scenarios, use_container_width=True)
    
    # Interest saved chart
    st.markdown("#### Interest Saved by Quarterly Amount")
    
    fig_saved = go.Figure()
    fig_saved.add_trace(go.Bar(
        x=[s["Quarterly"] for s in scenario_data if s["_saved"] > 0],
        y=[s["_saved"] for s in scenario_data if s["_saved"] > 0],
        marker_color=[
            "#34d399" if s["Quarterly"] == f"${quarterly:,.0f}" else "rgba(52,211,153,0.3)"
            for s in scenario_data if s["_saved"] > 0
        ],
        text=[f"${s['_saved']:,.0f}" for s in scenario_data if s["_saved"] > 0],
        textposition="outside",
        textfont=dict(size=11),
    ))
    
    fig_saved.update_layout(
        height=350,
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(17,24,39,0.5)",
        font_color="#94a3b8",
        xaxis_title="Quarterly Payment Amount",
        yaxis_title="Interest Saved ($)",
        yaxis=dict(gridcolor="rgba(30,41,59,0.5)", tickprefix="$"),
        xaxis=dict(gridcolor="rgba(30,41,59,0.5)"),
    )
    st.plotly_chart(fig_saved, use_container_width=True)
    
    # Custom scenario builder
    st.markdown("---")
    st.markdown("#### 🧪 Custom Scenario Builder")
    st.caption("Test a specific combination")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        custom_lump = st.number_input("Lump Sum ($)", 0, int(principal), initial_lump, 1000, key="custom_lump")
    with col2:
        custom_quarterly = st.number_input("Quarterly ($)", 0, 50000, quarterly, 500, key="custom_q")
    with col3:
        custom_monthly = st.number_input("Extra Monthly ($)", 0, 5000, extra_monthly, 25, key="custom_m")
    with col4:
        custom_rate = st.number_input("Rate (%)", 1.0, 30.0, rate, 0.25, key="custom_r")
    
    custom_result = calculate_loan(LoanConfig(
        principal=principal, annual_rate=custom_rate, term_years=term,
        initial_lump_sum=custom_lump, extra_monthly=custom_monthly,
        quarterly_payment=custom_quarterly, fixed_emi=fixed_emi,
    ))
    
    custom_original = calculate_loan(LoanConfig(principal=principal, annual_rate=custom_rate, term_years=term, fixed_emi=fixed_emi))
    custom_saved = custom_original.total_interest - custom_result.total_interest
    custom_time = custom_original.total_months - custom_result.total_months
    
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Payoff Time", format_time(custom_result.total_months))
    with c2:
        st.metric("Time Saved", format_time(custom_time))
    with c3:
        st.metric("Interest Saved", f"${custom_saved:,.0f}")
    with c4:
        st.metric("Monthly EMI", f"${custom_result.monthly_payment:,.0f}")


# ─────────────────────────────────────────────
# FOOTER
# ─────────────────────────────────────────────

st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #64748b; font-size: 12px; padding: 20px;">
    <strong>-Loan Payoff Optimizer</strong> • Built with ❤️ for financial freedom<br>
    <em>Remember: Every extra dollar toward a high-interest loan is a guaranteed return. 
    No investment beats certainty.</em><br><br>
    Run: <code>streamlit run loan_optimizer.py</code> • 
    Share with anyone who needs it
</div>
""", unsafe_allow_html=True)