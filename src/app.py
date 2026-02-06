import streamlit as st
import numpy as np
import pandas as pd

st.title("Fiat Redemption Fee Model")

st.markdown(
#    "**Formula:** `processing_fee = min(cap% * redemption_amount, max(0, fee_incurred - max(theoretical_edge, losses)))`"
    "**Formula:** `fee = max(0, min(cap% * redemption, fee_incurred - max(theo_edge, losses))`"
)

# --- Inputs ---
st.sidebar.header("Parameters")

deposit_amount = st.sidebar.slider("Deposit Amount ($)", 0, 9000, 100, step=50)
provider_fee_pct = st.sidebar.slider("Provider Fee (%)", 0.0, 10.0, 2.9, step=0.1)
provider_fee_fixed = st.sidebar.slider(
    "Provider Fixed Fee ($)", 0.0, 1.0, 0.30, step=0.05
)
house_edge_pct = st.sidebar.slider("House Edge (%)", 0.5, 5.0, 2.0, step=0.1)
redemption_fee_cap_pct = st.sidebar.slider(
    "Redemption Fee Cap (%)", 0.0, 10.0, 5.0, step=0.1
)

cashback_pct = st.sidebar.slider("Cashback Card (%)", 0.0, 5.0, 2.0, step=0.5)

# Playthrough multiplier: how many times the deposit is wagered
playthrough = st.sidebar.slider("Playthrough Multiplier (x)", 1.0, 20.0, 1.0, step=0.5)

# --- Derived Values ---
fee_incurred = deposit_amount * (provider_fee_pct / 100) + provider_fee_fixed
total_wagered = deposit_amount * playthrough
theoretical_edge = total_wagered * (house_edge_pct / 100)

# For modeling, assume actual losses ~ theoretical edge (expected value)
# But also show a slider for actual outcome variance
luck_factor = st.sidebar.slider(
    "Player Luck (0 = lost more than expected, 1 = broke even, >1 = won)",
    0.0, 2.0, 1.0, step=0.1
)

# actual losses: if luck_factor=1, losses = theoretical_edge
# if luck_factor=0, losses = 2x theoretical edge
# if luck_factor=2, losses = 0 (player ran hot)
actual_losses = theoretical_edge * (2 - luck_factor)
actual_losses = max(0, actual_losses)

redemption_amount = deposit_amount - actual_losses
redemption_amount = max(0, redemption_amount)

# --- Fee Calculation ---
uncovered_cost = fee_incurred - max(theoretical_edge, actual_losses)
uncovered_cost = max(0, uncovered_cost)
fee_cap = redemption_fee_cap_pct / 100 * redemption_amount
processing_fee = min(fee_cap, uncovered_cost)

net_redemption = redemption_amount - processing_fee

# --- Display ---
st.header("Scenario Breakdown")

col1, col2, col3 = st.columns(3)
col1.metric("Deposit", f"${deposit_amount:.2f}")
col2.metric("Provider Cost", f"${fee_incurred:.2f}")
col3.metric("Total Wagered", f"${total_wagered:.2f}")

col1, col2, col3 = st.columns(3)
col1.metric("Theoretical Edge", f"${theoretical_edge:.2f}")
col2.metric("Actual Losses", f"${actual_losses:.2f}")
col3.metric("Redemption Amount", f"${redemption_amount:.2f}")

col1, col2, col3 = st.columns(3)
col1.metric("Uncovered Cost", f"${uncovered_cost:.2f}")
col2.metric("Processing Fee Charged", f"${processing_fee:.2f}")
col3.metric("Net to Player", f"${net_redemption:.2f}")

# --- Abuser Scenario Table ---
st.header("Abuser Analysis: 1x Playthrough, Average Player")
st.markdown(
    "Shows expected abuser profit assuming statistical average losses (house edge). "
    "Over many attempts, every player converges to this."
)

deposits = np.arange(50, 9050, 50)
rows = []
for d in deposits:
    fi = d * (provider_fee_pct / 100) + provider_fee_fixed
    tw = d * 1.0  # 1x playthrough
    te = tw * (house_edge_pct / 100)
    losses = te  # average player loses the expected edge
    redemption = d - losses
    uc = max(0, fi - losses)
    cap = redemption_fee_cap_pct / 100 * redemption
    fee = min(cap, uc)
    cashback = d * (cashback_pct / 100)
    profit = cashback - fee - losses
    rows.append({
        "Deposit": d,
        "Provider Cost": round(fi, 2),
        "Edge Loss": round(losses, 2),
        "Uncovered": round(uc, 2),
        "Fee Charged": round(fee, 2),
        f"Cashback ({cashback_pct}%)": round(cashback, 2),
        "Abuser Profit": round(profit, 2),
    })

df = pd.DataFrame(rows)
st.dataframe(df, use_container_width=True)

profitable = df[df["Abuser Profit"] > 0]
if len(profitable) > 0:
    st.warning(f"Abuser is profitable at {len(profitable)}/{len(df)} deposit levels")
else:
    st.success("Abuser is unprofitable at all deposit levels with this fee structure")

# --- Break-Even Curve ---
st.header("Break-Even Analysis by Deposit")
st.markdown(
    "Shows expected abuser profit as a % of deposit. "
    "Assumes average player who loses the house edge over time."
)

import altair as alt

curve_rows = []
for d in deposits:
    if d == 0:
        continue
    fi = d * (provider_fee_pct / 100) + provider_fee_fixed
    te = d * (house_edge_pct / 100)
    losses = te
    redemption = d - losses
    uc = max(0, fi - losses)
    cap = redemption_fee_cap_pct / 100 * redemption
    fee = min(cap, uc)
    cashback = d * (cashback_pct / 100)
    profit = cashback - fee - losses
    profit_pct = (profit / d) * 100
    curve_rows.append({
        "Deposit": d,
        "Abuser Profit (%)": round(profit_pct, 3),
    })

curve_df = pd.DataFrame(curve_rows)

line = alt.Chart(curve_df).mark_line(color="#1f77b4").encode(
    x=alt.X("Deposit:Q", title="Deposit ($)"),
    y=alt.Y("Abuser Profit (%):Q", title="Abuser Profit (% of Deposit)"),
    tooltip=["Deposit", "Abuser Profit (%)"],
)

zero_line = alt.Chart(curve_df).mark_rule(
    strokeDash=[5, 5], color="#e45756"
).encode(y=alt.datum(0))

st.altair_chart(line + zero_line, use_container_width=True)

st.caption(
    "Blue = expected abuser profit % · "
    "Red dashed = break-even line"
)

# Find crossover point
crossover = None
for row in curve_rows:
    if row["Abuser Profit (%)"] > 0:
        crossover = row["Deposit"]
        break

if crossover:
    st.warning(
        f"Abuser becomes profitable above ${crossover} deposits."
    )
else:
    st.success("Abuser is unprofitable at all deposit levels in expectation.")
