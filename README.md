# PayoffPilot - Loan Payoff Optimizer

A powerful, interactive loan payoff calculator built with Python & Streamlit. Model lump sums, quarterly payments, monthly extras, and **erratic one-time payments** to see exactly how to pay off your loan faster.

![Python](https://img.shields.io/badge/Python-3.8+-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-1.30+-red)

## Features

| Feature | Description |
|---------|-------------|
|  **Configurable Inputs** | Loan amount, interest rate, tenure — all adjustable |
|  **Initial Lump Sum** | One-time upfront principal reduction |
|  **Quarterly Payments** | Recurring extra payments every 3 months |
|  **Extra Monthly Payments** | Additional amount on top of your EMI |
|  **Erratic Payments** | One-time payments at ANY specific month (bonus, tax refund, etc.) |
|  **Payoff Time Comparison** | See exactly how much faster you'll be debt-free |
|  **Monthly Installment Impact** | How prepayments change your effective EMI |
|  **Interest Saved Calculator** | Total interest eliminated by your strategy |
|  **Full Amortization Schedule** | Month-by-month breakdown, downloadable as CSV |
|  **Interactive Charts** | Balance curves, interest vs principal splits, scenario comparisons |
|  **Scenario Lab** | Compare 7+ quarterly payment levels side by side |
|  **Custom Scenario Builder** | Test any combination of parameters |

## Quick Start

### 1. Install Python
Make sure you have Python 3.8+ installed. Download from [python.org](https://python.org).

### 2. Clone or Download
Save the project folder to your machine.

### 3. Install Dependencies

```bash
cd loan-optimizer
pip install -r requirements.txt
```

### 4. Run the App

```bash
streamlit run loan_optimizer.py
```

The app will open in your browser at `http://localhost:8501`.

## How to Use

### Sidebar Controls
- **Loan Details**: Set your principal, rate, and term
- **Early Payment Options**: Configure lump sum, quarterly, and monthly extras
- **Erratic Payments**: Add one-time payments at specific months

### Tabs
1. **📊 Dashboard** — Overview with key metrics, comparison table, and balance chart
2. **📅 Payoff Timeline** — See how each payment layer accelerates payoff
3. **🎯 Erratic Payments** — Deep analysis of ad-hoc payment impact with ROI
4. **📋 Amortization Schedule** — Full month-by-month table (downloadable)
5. **🔬 Scenario Lab** — Compare quarterly amounts and build custom scenarios

### Example: Erratic Payment
Got a $2,000 bonus at month 6? 
1. Go to sidebar → "Ad-Hoc / Erratic Payments"
2. Click "Add an erratic payment"
3. Set month to 6, amount to 2000
4. Click "Add Payment"
5. Check the "Erratic Payments Impact" tab to see the ROI

## The Math Behind It

Every dollar prepaid on a loan saves you `(interest_rate)%` per year in interest, compounded over the remaining life of the loan. On a 13% loan:

- **$1,000 prepaid at month 6** → saves ~$2,500+ in interest
- **$5,000 quarterly** → can cut a 15-year loan to ~4-5 years
- **Earlier payments save more** because they reduce the base that compounds

No stock market investment gives you a **guaranteed** 13% return. Loan prepayment does.

## Sharing with Others

This app works for ANY loan — student loans, mortgages, car payments, personal loans. Just change the inputs in the sidebar. Share the folder with anyone who could benefit.

## Tech Stack

- **Python 3.8+**
- **Streamlit** — Interactive web UI
- **Plotly** — Charts and visualizations
- **Pandas** — Data handling

## Live Link:
You can access the calculator here: https://rechita-loan-payoff-optimizer-loan-optimizer-ipd2od.streamlit.app/
## License

Free to use, share, and modify. Built with ❤️ for financial freedom.
