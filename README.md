# RWA Calculator

A comprehensive Basel III/IV Risk-Weighted Assets calculator implementing all major regulatory approaches.

## Installation

```bash
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt
```

## Quick Start

```python
from rwa_calc import calculate_rwa, calculate_sa_rwa, compare_all_approaches

# IRB calculation
result = calculate_rwa(ead=1_000_000, pd=0.02, lgd=0.45, maturity=2.5)
print(f"RWA: ${result['rwa']:,.0f}, Risk Weight: {result['risk_weight_pct']:.1f}%")

# SA calculation
result = calculate_sa_rwa(ead=1_000_000, exposure_class="corporate", rating="BBB")
print(f"RWA: ${result['rwa']:,.0f}, Risk Weight: {result['risk_weight_pct']:.0f}%")
```

## Modules

| Module | Description |
|--------|-------------|
| `rwa_calc.py` | Credit risk (SA-CR, F-IRB, A-IRB) and securitization (SEC-SA, SEC-IRBA, ERBA, IAA) |
| `counterparty_risk.py` | SA-CCR and CVA (BA-CVA, SA-CVA) |
| `market_risk.py` | FRTB-SA (SbM, DRC, RRAO) |
| `operational_risk.py` | SMA |
| `capital_framework.py` | Output floor, leverage ratio, large exposures, CRM, CCF |
| `total_capital.py` | Integration module for total capital calculation |

## Implemented Methodologies

### Credit Risk

#### SA-CR (Standardised Approach)
```python
from rwa_calc import calculate_sa_rwa

result = calculate_sa_rwa(
    ead=1_000_000,
    exposure_class="corporate",  # sovereign, bank, corporate, retail, residential_re, commercial_re
    rating="BBB",
    is_sme=False,  # SME supporting factor
    ltv=0.75,      # for real estate
)
```

#### F-IRB (Foundation IRB)
```python
from rwa_calc import calculate_rwa

result = calculate_rwa(
    ead=1_000_000,
    pd=0.02,        # Bank-estimated PD
    lgd=0.45,       # Regulatory LGD (45% senior unsecured)
    maturity=2.5,
    asset_class="corporate"  # corporate, retail_mortgage, retail_revolving, retail_other
)
```

#### A-IRB (Advanced IRB)
```python
from rwa_calc import calculate_airb_rwa

result = calculate_airb_rwa(
    ead=1_000_000,
    pd=0.02,        # Bank-estimated PD
    lgd=0.30,       # Bank-estimated LGD
    maturity=2.5,
    asset_class="corporate"
)
```

### Securitization

#### SEC-SA
```python
from rwa_calc import calculate_sec_sa_rwa

result = calculate_sec_sa_rwa(
    ead=1_000_000,
    attachment=0.05,   # 5%
    detachment=0.10,   # 10%
    ksa=0.08,          # Pool capital under SA
    n=50,              # Number of exposures
    is_sts=False       # STS securitization
)
```

#### SEC-IRBA
```python
from rwa_calc import calculate_sec_irba_rwa

result = calculate_sec_irba_rwa(
    ead=1_000_000,
    attachment=0.05,
    detachment=0.10,
    kirb=0.06,  # Pool capital under IRB
    n=50
)
```

#### ERBA
```python
from rwa_calc import calculate_erba_rwa

result = calculate_erba_rwa(
    ead=1_000_000,
    rating="BBB",
    seniority="senior",  # senior or non_senior
    maturity=5.0
)
```

### Counterparty Credit Risk

#### SA-CCR
```python
from counterparty_risk import calculate_sa_ccr_ead

trades = [
    {"notional": 10_000_000, "asset_class": "IR", "maturity": 5.0, "mtm": 100_000, "delta": 1.0},
    {"notional": 5_000_000, "asset_class": "FX", "maturity": 1.0, "mtm": 50_000, "delta": 1.0},
]

result = calculate_sa_ccr_ead(
    trades,
    collateral_held=50_000,
    is_margined=True
)
print(f"EAD: ${result['ead']:,.0f}")
```

#### CVA Risk
```python
from counterparty_risk import calculate_ba_cva

counterparties = [
    {"ead": 5_000_000, "rating": "A", "maturity": 3.0},
    {"ead": 3_000_000, "rating": "BBB", "maturity": 5.0},
]

result = calculate_ba_cva(counterparties)
print(f"CVA RWA: ${result['rwa']:,.0f}")
```

### Market Risk (FRTB-SA)

```python
from market_risk import calculate_frtb_sa, calculate_drc_charge

# Delta sensitivities
delta_positions = {
    "EQ": [{"bucket": "large_cap_developed", "sensitivity": 1_000_000, "risk_weight": 20}]
}

# DRC positions
drc_positions = [
    {"obligor": "Corp_A", "notional": 5_000_000, "rating": "A", "seniority": "senior", "is_long": True}
]

result = calculate_frtb_sa(
    delta_positions=delta_positions,
    drc_positions=drc_positions
)
print(f"Total Market Risk RWA: ${result['total_rwa']:,.0f}")
```

### Operational Risk (SMA)

```python
from operational_risk import calculate_sma_capital

result = calculate_sma_capital(
    bi=2_000_000_000,           # Business Indicator
    average_annual_loss=100_000_000,  # 10-year average
    use_ilm=True
)
print(f"Op Risk RWA: ${result['rwa']:,.0f}")
```

### Capital Framework

#### Output Floor
```python
from capital_framework import calculate_output_floor

result = calculate_output_floor(
    rwa_irb=80_000_000_000,
    rwa_standardised=120_000_000_000,
    year=2028  # 72.5% floor
)
print(f"Floored RWA: ${result['floored_rwa']:,.0f}")
print(f"Floor binding: {result['floor_is_binding']}")
```

#### Leverage Ratio
```python
from capital_framework import calculate_leverage_ratio

result = calculate_leverage_ratio(
    tier1_capital=50_000_000_000,
    on_balance_sheet=1_000_000_000_000,
    derivatives_exposure=100_000_000_000,
    sft_exposure=50_000_000_000,
    off_balance_sheet=200_000_000_000
)
print(f"Leverage Ratio: {result['leverage_ratio_pct']:.2f}%")
```

#### Credit Risk Mitigation
```python
from capital_framework import calculate_exposure_with_crm

result = calculate_exposure_with_crm(
    exposure_value=100_000_000,
    collateral=[
        {"type": "cash", "value": 20_000_000},
        {"type": "sovereign_debt", "value": 30_000_000, "rating": "AA"},
    ],
    guarantee_value=20_000_000,
    guarantor_rw=0.20,
    exposure_rw=1.00
)
print(f"RWA after CRM: ${result['rwa_after_crm']:,.0f}")
```

## Total Capital Calculation

```python
from total_capital import calculate_total_rwa, calculate_capital_ratios

result = calculate_total_rwa(
    credit_exposures_irb=[...],
    securitization_exposures=[...],
    derivative_trades=[...],
    business_indicator=2_000_000_000,
    apply_output_floor=True
)

ratios = calculate_capital_ratios(
    total_rwa=result["total_rwa"],
    cet1_capital=80_000_000_000,
    at1_capital=10_000_000_000,
    tier2_capital=15_000_000_000
)
print(f"CET1 Ratio: {ratios['cet1_ratio_pct']:.1f}%")
```

## Risk Weight Comparison Tables

### Credit Risk (Corporate, $1M exposure)

| Rating | SA-CR | F-IRB | A-IRB (30% LGD) |
|--------|-------|-------|-----------------|
| AAA    | 20%   | 14%   | 10%             |
| A      | 50%   | 28%   | 19%             |
| BBB    | 75%   | 63%   | 42%             |
| BB     | 100%  | 115%  | 77%             |
| B      | 100%  | 186%  | 124%            |

### Securitization (Mezzanine 5-10%)

| Approach | Risk Weight |
|----------|-------------|
| SEC-IRBA | 37%         |
| SEC-SA   | 65%         |
| ERBA     | 120%        |
| IAA      | 150%        |

## References

- Basel III: Finalising post-crisis reforms (BCBS d424)
- CRE: Credit Risk (CRE20-CRE40)
- MAR: Market Risk (MAR20-MAR23, MAR50)
- OPE: Operational Risk (OPE25)
- CAP: Capital Framework (CAP30)
- LEV: Leverage Ratio (LEV30)
- LEX: Large Exposures (LEX30)
