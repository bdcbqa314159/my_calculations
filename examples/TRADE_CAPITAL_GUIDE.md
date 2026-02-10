# Trade-Level Full Capital Calculation Guide

How to compute the complete capital stack — Credit RWA + Market Risk (FRTB-SA, FRTB-IMA, and IRC) — for CDS, TRS, Repo, and CLN trades.

## Quick Start

```bash
cd rwa_calc

# Run all four examples
./venv/bin/python examples/cds_full_capital.py
./venv/bin/python examples/trs_full_capital.py
./venv/bin/python examples/repo_full_capital.py
./venv/bin/python examples/cln_full_capital.py
```

---

## Capital Pillars by Trade Type

Not every trade generates every type of capital charge. This matrix shows which pillars apply:

| Pillar | CDS | TRS | Repo | CLN |
|---|---|---|---|---|
| **CCR (SA-CCR)** | Yes | Yes | Yes (Comprehensive Approach) | **No** (funded) |
| **CVA** | Yes (BA-CVA) | Yes (BA-CVA) | **No** (SFT exempt) | **No** (funded) |
| **Credit Risk** | Seller only (ref entity) | Receiver only (underlying) | Net exposure E* | **Dual** (ref + issuer) |
| **FRTB-SA / IMA** | CSR delta + DRC | Depends on underlying | Banking book: none; Trading book: GIRR + CSR + DRC | CSR (×2) + GIRR + DRC (×2) |

---

## What's Different About Each Trade?

### CDS

**The direction matters most.** The protection buyer has short credit exposure; the seller has long.

- **CCR**: SA-CCR with `delta = -1` (buyer) or `+1` (seller). Asset class = credit (CR).
- **CVA**: BA-CVA on the dealer/counterparty.
- **Credit risk**: Only the protection seller has direct credit exposure to the reference entity.
- **ES risk factor**: Credit spread sensitivity (CS01) → `CR` risk class. Sub-category depends on the reference entity's rating:
  - IG → `"IG_corporate"` (40-day liquidity horizon)
  - HY → `"HY"` (60-day liquidity horizon)
- **DRC**: Reference entity is a DRC position. `is_long = True` for seller, `False` for buyer.
- **Key formula**: `CS01 ≈ notional × risky_duration × 1bp`. The 10-day ES ≈ `CS01 × spread_vol_10d × 2.338`.

```python
from cds_rwa import CDSTrade, calculate_cds_rwa
from frtb_ima import ESRiskFactor, DRCPosition, calculate_frtb_ima_capital

# Step 1: Credit RWA
credit = calculate_cds_rwa(trade)

# Step 2: Build ES risk factor from credit spread sensitivity
es_factor = ESRiskFactor("CR", "IG_corporate", es_10day=..., stressed_es_10day=...)

# Step 3: Build DRC position from reference entity
drc_pos = DRCPosition(..., obligor=ref_entity, pd=ref_pd, is_long=not is_buyer)

# Step 4: IMA capital
ima = calculate_frtb_ima_capital([es_factor], [drc_pos], config)
```

### TRS

**The underlying type determines the risk class.** This is the key difference from CDS.

- **CCR**: SA-CCR. Asset class depends on underlying (`EQ_SINGLE`, `CR_*`, `COM_*`).
- **CVA**: BA-CVA on the dealer.
- **Reference risk**: TRS receiver has synthetic long exposure to the underlying.
- **ES risk factor mapping**:
  - Equity underlying → `EQ` risk class (`large_cap` or `small_cap`)
  - Bond/loan/credit → `CR` risk class (`IG_corporate` or `HY`)
  - Commodity → `COM` risk class (`energy`, `precious_metals`, etc.)
- **DRC**: **Only for bond/loan/credit underlyings.** Equity and commodity TRS have no DRC.
- **Key insight**: An equity TRS has no default risk charge at all — only ES on equity vol.

```python
from trs_rwa import TRSTrade, calculate_trs_rwa

# The underlying type drives everything
if underlying == "equity":
    es_factor = ESRiskFactor("EQ", "large_cap", ...)   # no DRC
elif underlying == "bond":
    es_factor = ESRiskFactor("CR", "IG_corporate", ...) # has DRC
elif underlying == "commodity":
    es_factor = ESRiskFactor("COM", "energy", ...)      # no DRC
```

### Repo

**CVA exempt, often banking book, uses Comprehensive Approach for haircuts.**

- **CCR**: Comprehensive Approach (not SA-CCR). Formula:
  ```
  E* = max(0,  E×(1+He) − C×(1−Hc−Hfx))
  ```
  where He, Hc, Hfx are supervisory haircuts scaled by `sqrt(holding_period / 10)`.
- **CVA**: **Exempt** for all SFTs (MAR50.7).
- **Credit risk**: On the counterparty for the net exposure E*.
- **Market risk**: Most repos are **banking book** → no FRTB charges at all.
  If trading book: GIRR (interest rate on the bond) + CSR + DRC on the bond issuer.
- **Key insight**: A banking-book repo only generates CCR RWA. No CVA, no market risk.

```python
from repo_rwa import RepoTrade, calculate_repo_rwa

# Step 1: Credit RWA (Comprehensive Approach — always)
credit = calculate_repo_rwa(trade)
# credit['cva'] = {'cva_charge': 0, 'rwa': 0}  ← exempt

# Step 2: Market risk — only if trading book
if is_trading_book:
    # GIRR on the bond + CSR on the issuer spread + DRC on the issuer
    ...
```

### CLN (Credit-Linked Note)

**Funded instrument with dual credit exposure — no CCR, no CVA.**

- **CCR**: **None.** The investor pays cash upfront (funded).
- **CVA**: **None.** Not a derivative in the CCR sense.
- **Credit risk**: Dual default exposure — the investor loses if **either** the reference entity **or** the issuer defaults. Under SA-CR: first-to-default treatment uses the higher risk weight.
- **ES risk factors**: **Three** factors:
  1. Reference entity credit spread → `CR` risk class
  2. Issuer credit spread → `CR` risk class (may be different sub-category)
  3. Interest rate risk on the fixed coupon → `IR` risk class
- **DRC**: **Two** positions — reference entity AND issuer. When both are in the same sector, the systematic correlation is higher (wrong-way risk).
- **Key insight**: A CLN concentrates wrong-way risk when issuer and reference are correlated. The DRC Monte Carlo captures this through the systematic factor.

```python
from rwa_calc import calculate_sa_rwa

# No CCR, no CVA
credit_rwa = max(sa_rw_reference, sa_rw_issuer) * notional  # first-to-default

# ES: three risk factors
es_factors = [
    ESRiskFactor("CR", ref_sub, ...),    # reference spread
    ESRiskFactor("CR", iss_sub, ...),    # issuer spread
    ESRiskFactor("IR", "major", ...),    # rate risk
]

# DRC: two correlated positions
drc_positions = [
    DRCPosition(..., obligor=reference, systematic_factor=rho),
    DRCPosition(..., obligor=issuer, systematic_factor=rho),
]
```

---

## Step-by-Step Workflow

For any trade, the workflow is:

### 1. Define the trade

Use the appropriate dataclass (`CDSTrade`, `TRSTrade`, `RepoTrade`, or build your own for CLN).

### 2. Calculate Credit RWA

```python
credit_result = calculate_xxx_rwa(trade)  # cds/trs/repo
```

This handles CCR, CVA, and direct credit exposure in one call. For CLN, use `calculate_sa_rwa()` with first-to-default logic.

### 3. Map the trade to FRTB risk factors

This is the trade-specific step. You need to determine:
- **Which risk class?** (IR, EQ, FX, CR, COM)
- **Which sub-category?** (determines the liquidity horizon for ES)
- **What is the 10-day ES?** (from sensitivity × volatility × 2.338)
- **Is there a DRC position?** (only for credit underlyings)
- **What direction?** (long or short, driven by trade economics)

### 4. Calculate FRTB-SA

```python
from market_risk import calculate_frtb_sa

sa_result = calculate_frtb_sa(
    delta_positions={"CSR": [...]},
    drc_positions=[...],
)
```

### 5. Calculate FRTB-IMA

```python
from frtb_ima import calculate_frtb_ima_capital, ESRiskFactor, DRCPosition

ima_result = calculate_frtb_ima_capital(
    risk_factors=[ESRiskFactor(...)],
    drc_positions=[DRCPosition(...)],
    config=FRTBIMAConfig(...),
)
```

### 6. Combine

```
Total RWA = Credit RWA + max(Market RWA_SA, Market RWA_IMA)
```

In practice, a bank uses either SA or IMA for each desk (based on PLA test results), not both.

---

## ES 10-Day Estimation Rule of Thumb

For any sensitivity measure `s` (CS01, DV01, equity delta × spot, etc.):

```
ES_10day ≈ s × volatility_10day × 2.338
```

where:
- `volatility_10day` = annualized vol × sqrt(10/252)
- `2.338` = ES/VaR ratio at 97.5% confidence for normal distribution

Stressed ES uses a higher volatility (typically 1.5–2× current vol).

---

## Liquidity Horizon Reference

| Risk Factor | Sub-Category | LH (days) |
|---|---|---|
| IR | major currencies | 10 |
| IR | other | 20 |
| CR | IG sovereign | 20 |
| CR | IG corporate | 40 |
| EQ | large cap | 40 |
| FX | major pairs | 40 |
| CR | HY | 60 |
| EQ | small cap | 60 |
| COM | energy, precious metals | 60 |
| FX | other | 60 |
| EQ | other | 120 |
| COM | other | 120 |
| CR | other | 120 |

---

## IRC (Incremental Risk Charge) — Basel 2.5

For trading book credit positions, IRC captures both **default risk** and **rating migration risk** over a 1-year horizon at 99.9% confidence.

### When to Use IRC vs FRTB-IMA DRC

| Framework | Default Risk | Migration Risk | Applies To |
|---|---|---|---|
| **IRC** (Basel 2.5) | Yes | Yes (spread widening) | Trading book credit |
| **FRTB-IMA DRC** | Yes | No (in ES via spreads) | Trading book credit |
| **FRTB-SA DRC** | Yes | No | Trading book credit |

Under FRTB, migration risk is captured in the ES component via credit spread sensitivity. Under Basel 2.5, it's in IRC.

### IRC Inputs

Each position needs:

```python
from irc import IRCPosition, IRCConfig, calculate_irc

position = IRCPosition(
    position_id="bond_1",
    issuer="Corp A",           # obligor name
    notional=10_000_000,
    market_value=10_200_000,
    rating="BBB",              # current rating (AAA to CCC)
    tenor_years=5.0,           # remaining maturity
    seniority="senior_unsecured",  # affects LGD
    sector="corporate",
    liquidity_horizon_months=3,    # rebalancing frequency
    is_long=True,
    coupon_rate=0.045,
)
```

### IRC Monte Carlo Process

```
For each simulation (100,000+):
    1. Draw systematic factor X ~ N(0,1)
    2. For each issuer:
       Z_i = ρ × X + √(1-ρ²) × ε_i
       U_i = Φ(Z_i)  # convert to uniform
       new_rating = simulate_migration(current_rating, U_i)
    3. Calculate loss:
       - Default: loss = LGD × notional
       - Migration: loss = Δspread × PV01

IRC = 99.9th percentile of loss distribution
```

### Rating Transition Matrix

The simulation uses historical 1-year transition probabilities:

| From | Upgrade | Stable | Downgrade | Default |
|---|---|---|---|---|
| AAA | 0.0% | 90.8% | 9.2% | 0.00% |
| AA | 0.7% | 90.7% | 8.6% | 0.02% |
| A | 2.4% | 91.1% | 6.5% | 0.06% |
| BBB | 6.3% | 86.9% | 6.6% | 0.18% |
| BB | 8.6% | 80.5% | 9.8% | 1.06% |
| B | 7.3% | 83.0% | 4.6% | 5.21% |
| CCC | 15.4% | 64.9% | 0.0% | 19.78% |

### Example: IRC Calculation

```python
from irc import IRCPosition, IRCConfig, calculate_irc, calculate_irc_by_issuer

positions = [
    IRCPosition("b1", "Corp_A", 10_000_000, 10_000_000, "BBB", 5.0),
    IRCPosition("b2", "Corp_B", 8_000_000, 8_000_000, "BB", 4.0),
    IRCPosition("b3", "Corp_C", 6_000_000, 6_000_000, "A", 7.0),
]

config = IRCConfig(
    num_simulations=100_000,
    systematic_correlation=0.50,
)

result = calculate_irc(positions, config)
print(f"IRC: ${result['irc']:,.0f}")
print(f"IRC RWA: ${result['rwa']:,.0f}")

# Per-issuer contribution
issuer_result = calculate_irc_by_issuer(positions, config)
for c in issuer_result["issuer_contributions"]:
    print(f"{c['issuer']}: ${c['marginal_irc']:,.0f} ({c['pct_of_total']:.1f}%)")
```

### IRC Example Script

```bash
./venv/bin/python examples/irc_full_example.py
```
