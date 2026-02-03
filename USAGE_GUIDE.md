# RWA Calculator Usage Guide

How to use each product-specific RWA calculator: what inputs you need, what defaults are available, and what the output contains.

---

## CDS (`cds_rwa.py`)

### Quick Start

```python
from cds_rwa import quick_cds_rwa

result = quick_cds_rwa(
    notional=10_000_000,  # CDS notional
    pd=0.02,              # reference entity PD (2%)
    maturity=5.0,         # years
)
```

### Quick Function Parameters

| Parameter | Required | Default | What it controls |
|---|---|---|---|
| `notional` | Yes | — | CDS notional amount |
| `pd` | Yes | — | Reference entity probability of default |
| `maturity` | Yes | — | Remaining maturity in years |
| `is_protection_buyer` | No | `True` | Your direction — buyer has no credit risk on ref entity, seller does |
| `spread_bps` | No | `100.0` | Current CDS spread in bps, used to estimate MTM for SA-CCR |
| `counterparty_rating` | No | `"A"` | Dealer rating — drives CCR risk weight and CVA charge |
| `approach` | No | `"sa"` | `"sa"` or `"irb"` — how counterparty/ref entity RW is calculated |
| `book` | No | `"banking"` | `"banking"` or `"trading"` — trading book adds a market risk charge |

### Full Control via CDSTrade

```python
from cds_rwa import CDSTrade, calculate_cds_rwa

trade = CDSTrade(
    notional=10_000_000,
    maturity=5.0,
    is_protection_buyer=True,
    is_index=False,                    # single-name vs index CDS
    spread_bps=150.0,
    mtm=None,                          # auto-estimated from spread if None
    recovery_rate=0.40,

    # Reference entity — provide PD or rating (either works, the other is inferred)
    reference_entity_pd=0.02,
    reference_entity_rating=None,
    reference_entity_sector="corporate",

    # Counterparty — provide PD or rating
    counterparty_pd=None,
    counterparty_rating="A",
    counterparty_sector="financial",

    # Regulatory
    approach="sa",                     # "sa" or "irb"
    book="banking",                    # "banking" or "trading"

    # Collateral (for SA-CCR)
    collateral_held=0.0,
    collateral_posted=0.0,
    is_margined=False,
)

result = calculate_cds_rwa(trade)
```

### What You Need to Know About Your Trade

1. **Notional + maturity** — the economics
2. **Direction** — `is_protection_buyer` determines whether you bear credit risk on the reference entity (seller does, buyer doesn't)
3. **Reference entity credit quality** — either `reference_entity_pd` or `reference_entity_rating`; one is enough
4. **Counterparty credit quality** — either `counterparty_pd` or `counterparty_rating`; one is enough
5. **Spread** — used to estimate MTM if you don't provide `mtm` directly

### Output Breakdown

| Key | What it contains |
|---|---|
| `result["ccr"]` | Counterparty credit risk — SA-CCR EAD risk-weighted against the dealer |
| `result["cva"]` | CVA risk charge — BA-CVA on the dealer |
| `result["credit_risk"]` | Direct credit risk on the reference entity (zero for protection buyers) |
| `result["market_risk"]` | Specific risk charge (zero unless `book="trading"`) |
| `result["total_rwa"]` | Sum of all RWA components |
| `result["total_capital"]` | `total_rwa * 8%` |

### Comparison Helper

```python
from cds_rwa import compare_buyer_vs_seller

comp = compare_buyer_vs_seller(10_000_000, pd=0.02, maturity=5.0)
# comp["comparison"]["buyer_total_rwa"]
# comp["comparison"]["seller_total_rwa"]
```

---

## Loan (`loan_rwa.py`)

### Quick Start

```python
from loan_rwa import quick_loan_rwa

result = quick_loan_rwa(
    total_commitment=50_000_000,  # total facility size
    drawn=30_000_000,             # amount currently drawn
    pd=0.01,                      # borrower PD (1%)
    maturity=3.0,                 # years
)
```

### Quick Function Parameters

| Parameter | Required | Default | What it controls |
|---|---|---|---|
| `total_commitment` | Yes | — | Total facility amount |
| `drawn` | No | `total_commitment` | Amount currently drawn (defaults to fully drawn) |
| `pd` | No | `0.01` | Borrower probability of default |
| `maturity` | No | `3.0` | Remaining maturity in years |
| `approach` | No | `"sa"` | `"sa"`, `"firb"`, or `"airb"` |
| `is_revolving` | No | `False` | Whether the facility is revolving/committed |
| `borrower_sector` | No | `"corporate"` | Borrower sector for SA risk weight lookup |

### Full Control via LoanTrade

```python
from loan_rwa import LoanTrade, calculate_loan_rwa

trade = LoanTrade(
    # Core economics
    total_commitment=50_000_000,
    drawn_amount=30_000_000,
    maturity=3.0,
    is_revolving=True,

    # Borrower — provide PD or rating (either works, the other is inferred)
    borrower_pd=0.01,
    borrower_rating=None,
    borrower_sector="corporate",       # used for SA exposure class
    is_sme=False,
    sales_turnover=None,               # EUR millions, for IRB SME correlation adjustment

    # Collateral & guarantees (for CRM)
    collateral=[                       # list of dicts
        {"type": "cash", "value": 5_000_000},
        {"type": "sovereign_debt", "value": 10_000_000, "rating": "AA", "maturity": "5y"},
    ],
    guarantee_value=0.0,
    guarantor_rw=None,                 # risk weight of guarantor (for substitution approach)

    # Regulatory
    approach="sa",                     # "sa", "firb", or "airb"
    commitment_type="commitment_over_1y",  # drives the CCF for undrawn portion
    borrower_lgd=None,                 # bank-estimated LGD, only used for A-IRB
)

result = calculate_loan_rwa(trade)
```

### What You Need to Know About Your Trade

1. **Commitment + drawn amount** — total facility and how much is drawn; the undrawn portion gets a CCF
2. **Borrower credit quality** — either `borrower_pd` or `borrower_rating`; one is enough
3. **Approach** — `"sa"` uses rating-based risk weights, `"firb"` uses prescribed LGD (45%), `"airb"` uses your own LGD estimate
4. **Revolving flag** — if `is_revolving=True` or `drawn < total_commitment`, a CCF is applied to the undrawn portion
5. **Commitment type** — drives which CCF applies (e.g. `"commitment_over_1y"` = 40%, `"commitment_unconditionally_cancellable"` = 10%)
6. **Collateral** (optional) — reduces exposure via CRM haircut approach
7. **SME flag** (optional) — `is_sme=True` gives a lower SA risk weight; `sales_turnover` triggers the IRB SME correlation adjustment

### Output Breakdown

| Key | What it contains |
|---|---|
| `result["ead"]` | EAD calculation: drawn, undrawn, CCF, final EAD |
| `result["credit_risk"]` | Credit risk RWA on the borrower (before CRM), risk weight |
| `result["crm"]` | Exposure and RWA after credit risk mitigation |
| `result["ccr"]` | Always zero — loans are not derivatives |
| `result["cva"]` | Always zero — loans are not subject to CVA |
| `result["market_risk"]` | Always zero — banking book |
| `result["total_rwa"]` | CRM-adjusted RWA (the final figure) |
| `result["total_capital"]` | `total_rwa * 8%` |

### Valid Commitment Types

These drive the CCF applied to the undrawn portion:

| `commitment_type` | SA CCF | Description |
|---|---|---|
| `"commitment_unconditionally_cancellable"` | 10% | Can be cancelled anytime without notice |
| `"commitment_1y_or_less"` | 20% | Commitment with maturity <= 1 year |
| `"commitment_over_1y"` | 40% | Commitment with maturity > 1 year |
| `"direct_credit_substitute"` | 100% | Standby LCs, guarantees |
| `"transaction_related"` | 50% | Performance bonds, bid bonds |

### Comparison Helper

```python
from loan_rwa import compare_approaches

comp = compare_approaches(50_000_000, pd=0.01, maturity=3.0)
# comp["comparison"]["sa_rwa"]
# comp["comparison"]["firb_rwa"]
# comp["comparison"]["airb_rwa"]
```

---

## Total Return Swap (`trs_rwa.py`)

### Quick Start

```python
from trs_rwa import quick_trs_rwa

result = quick_trs_rwa(
    notional=10_000_000,       # TRS notional
    pd=0.02,                   # underlying reference asset PD
    maturity=3.0,              # years
)
```

### Quick Function Parameters

| Parameter | Required | Default | What it controls |
|---|---|---|---|
| `notional` | Yes | — | TRS notional amount |
| `pd` | No | `0.02` | PD of the underlying reference asset |
| `maturity` | No | `3.0` | Remaining maturity in years |
| `is_total_return_receiver` | No | `True` | Receiver = synthetic long on underlying |
| `underlying_type` | No | `"equity"` | Type of underlying (see table below) |
| `counterparty_rating` | No | `"A"` | Dealer credit rating |
| `approach` | No | `"sa"` | `"sa"` or `"irb"` |
| `book` | No | `"banking"` | `"banking"` or `"trading"` — trading book adds FRTB-SA delta charge |

### Full Control via TRSTrade

```python
from trs_rwa import TRSTrade, calculate_trs_rwa

trade = TRSTrade(
    # Core economics
    notional=10_000_000,
    maturity=3.0,
    is_total_return_receiver=True,     # receiver = synthetic long
    mtm=None,                          # auto-estimated if None
    spread_bps=50.0,                   # total return spread
    funding_spread_bps=20.0,           # funding leg spread

    # Underlying reference asset — provide PD or rating
    underlying_type="equity",          # equity, equity_index, bond, loan, credit, credit_index, commodity
    underlying_rating=None,
    underlying_pd=0.02,
    underlying_sector="corporate",

    # Counterparty — provide PD or rating
    counterparty_pd=None,
    counterparty_rating="A",
    counterparty_sector="financial",

    # Regulatory
    approach="sa",                     # "sa" or "irb"
    book="banking",                    # "banking" or "trading"

    # Collateral (for SA-CCR)
    collateral_held=0.0,
    collateral_posted=0.0,
    is_margined=False,
)

result = calculate_trs_rwa(trade)
```

### What You Need to Know About Your Trade

1. **Notional + maturity** — the economics
2. **Direction** — `is_total_return_receiver=True` means you have a synthetic long on the underlying (you bear reference asset risk); payer does not
3. **Underlying type** — determines the SA-CCR asset class for CCR and the FRTB bucket for market risk
4. **Underlying credit quality** — either `underlying_pd` or `underlying_rating`; one is enough
5. **Counterparty credit quality** — either `counterparty_pd` or `counterparty_rating`; one is enough
6. **Book** — `"trading"` adds an FRTB-SA delta sensitivity market risk charge

### Valid Underlying Types

| `underlying_type` | SA-CCR Asset Class | FRTB Risk Class |
|---|---|---|
| `"equity"` | `EQ_SINGLE` | EQ |
| `"equity_index"` | `EQ_INDEX` | EQ |
| `"bond"` / `"loan"` / `"credit"` | `CR_*` (by rating) | CSR |
| `"credit_index"` | `CR_INDEX_IG` / `CR_INDEX_SG` | CSR |
| `"commodity"` | `COM_OTHER` | COM |

### Output Breakdown

| Key | What it contains |
|---|---|
| `result["ccr"]` | Counterparty credit risk — SA-CCR EAD risk-weighted against the dealer |
| `result["cva"]` | CVA risk charge — BA-CVA on the dealer |
| `result["reference_risk"]` | Credit/asset risk on the underlying (zero for payers) |
| `result["market_risk"]` | FRTB-SA delta charge (zero unless `book="trading"`) |
| `result["total_rwa"]` | Sum of all RWA components |
| `result["total_capital"]` | `total_rwa * 8%` |

### Comparison Helper

```python
from trs_rwa import compare_receiver_vs_payer

comp = compare_receiver_vs_payer(10_000_000, pd=0.02, maturity=3.0, underlying_type="equity")
# comp["comparison"]["receiver_total_rwa"]
# comp["comparison"]["payer_total_rwa"]
```

---

## Repo / Reverse Repo (`repo_rwa.py`)

### Quick Start

```python
from repo_rwa import quick_repo_rwa

result = quick_repo_rwa(
    cash_amount=50_000_000,              # cash leg
    securities_value=51_000_000,         # securities leg (market value)
    maturity=0.25,                       # years (~ 3 months)
)
```

### Quick Function Parameters

| Parameter | Required | Default | What it controls |
|---|---|---|---|
| `cash_amount` | Yes | — | Cash leg of the repo |
| `securities_value` | No | `cash * 1.02` | Market value of the securities leg (defaults to 2% overcollateralisation) |
| `maturity` | No | `0.25` | Remaining maturity in years |
| `is_repo` | No | `True` | `True` = repo (lend securities, borrow cash); `False` = reverse repo (lend cash, borrow securities) |
| `security_type` | No | `"sovereign_debt"` | Type of securities (see table below) |
| `security_rating` | No | `"AAA"` | Rating of the securities issuer |
| `counterparty_rating` | No | `"A"` | Counterparty credit rating |
| `approach` | No | `"sa"` | `"sa"` or `"irb"` |

### Full Control via RepoTrade

```python
from repo_rwa import RepoTrade, calculate_repo_rwa

trade = RepoTrade(
    # Core economics
    cash_amount=50_000_000,
    securities_value=51_000_000,
    maturity=0.25,

    # Direction
    is_repo=True,                      # True = repo, False = reverse repo

    # Securities characteristics
    security_type="sovereign_debt",    # sovereign_debt, corporate_bond, equity_main_index, equity_other, cash, gold
    security_rating="AAA",             # issuer rating
    security_maturity_bucket="5y",     # 1y, 5y, long

    # Counterparty — provide PD or rating
    counterparty_pd=None,
    counterparty_rating="A",
    counterparty_sector="financial",

    # Haircut parameters
    currency_mismatch=False,           # adds FX haircut (8% base, scaled)
    holding_period_days=5,             # standard is 5 for repos; haircuts scale with sqrt(HP/10)

    # Regulatory
    approach="sa",                     # "sa" or "irb"
    haircut_approach="supervisory",    # "supervisory" or "own_estimates"
)

result = calculate_repo_rwa(trade)
```

### What You Need to Know About Your Trade

1. **Cash amount + securities value** — the two legs of the repo
2. **Direction** — `is_repo=True` means you lend securities and receive cash (your exposure is the securities); `False` means you lend cash and receive securities (your exposure is the cash)
3. **Security type + rating + maturity bucket** — determines the supervisory haircut applied to the securities
4. **Counterparty credit quality** — either `counterparty_pd` or `counterparty_rating`; one is enough
5. **Holding period** — default 5 days for repos; haircuts scale with `sqrt(holding_period / 10)`
6. **Currency mismatch** — set `True` if securities and cash are in different currencies (adds ~8% haircut)

### Valid Security Types

| `security_type` | Base Haircut (5y, AAA) | Description |
|---|---|---|
| `"sovereign_debt"` | 2.0% | Government bonds |
| `"corporate_bond"` | 4.0–6.0% | Corporate bonds (varies by rating) |
| `"equity_main_index"` | 15.0% | Main index equities |
| `"equity_other"` | 25.0% | Other listed equities |
| `"cash"` | 0.0% | Cash collateral |
| `"gold"` | 15.0% | Gold |

### How E* Is Calculated

The net exposure uses the comprehensive approach:

```
E* = max(0, E × (1 + He) - C × (1 - Hc - Hfx))
```

- **Repo**: E = securities value, C = cash, He = security haircut, Hc = 0
- **Reverse repo**: E = cash, C = securities value, He = 0, Hc = security haircut
- Haircuts are scaled by `sqrt(holding_period_days / 10)`

### Output Breakdown

| Key | What it contains |
|---|---|
| `result["exposure"]` | Comprehensive approach details: E*, haircuts, overcollateralisation % |
| `result["ccr"]` | Credit risk on E* — risk-weighted against the counterparty |
| `result["cva"]` | Always zero — SFTs are exempt from CVA per Basel III (MAR50.7) |
| `result["market_risk"]` | Always zero — banking book |
| `result["total_rwa"]` | RWA on the net exposure E* |
| `result["total_capital"]` | `total_rwa * 8%` |

### Comparison Helper

```python
from repo_rwa import compare_repo_vs_reverse

comp = compare_repo_vs_reverse(50_000_000, securities_value=51_000_000, maturity=0.25)
# comp["comparison"]["repo_total_rwa"]
# comp["comparison"]["reverse_total_rwa"]
```

---

## Summary: RWA Components by Product

| Component | CDS | Loan | TRS | Repo |
|---|---|---|---|---|
| **Counterparty Credit Risk** | SA-CCR EAD on dealer | N/A | SA-CCR EAD on dealer | E* via comprehensive approach |
| **CVA** | BA-CVA on dealer | N/A | BA-CVA on dealer | Exempt (MAR50.7) |
| **Credit Risk** | On ref entity (seller only) | On borrower (SA/F-IRB/A-IRB) | On underlying (receiver only) | On counterparty via E* |
| **CRM** | N/A | Collateral + guarantees | N/A | Supervisory haircuts |
| **CCF** | N/A | Undrawn commitments | N/A | N/A |
| **Market Risk** | Specific risk (trading book) | N/A | FRTB-SA delta (trading book) | N/A |
