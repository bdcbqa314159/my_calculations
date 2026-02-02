# RWA Calculator - API Reference

Comprehensive input/output documentation for all Basel II, Basel III/IV calculation functions.

---

## Table of Contents

### Basel III/IV
- [1. Core Credit Risk](#1-core-credit-risk-rwa_calcpy)
- [2. Counterparty Credit Risk](#2-counterparty-credit-risk-counterparty_riskpy)
- [3. Market Risk](#3-market-risk-market_riskpy)
- [4. Operational Risk](#4-operational-risk-operational_riskpy)
- [5. Capital Framework](#5-capital-framework-capital_frameworkpy)
- [6. Specialized Lending](#6-specialized-lending-specialized_lendingpy)
- [7. Liquidity](#7-liquidity-liquiditypy)
- [8. IRRBB](#8-irrbb-irrbpy)
- [9. Equity & CCP](#9-equity--ccp-equity_ccppy)
- [10. G-SIB & TLAC](#10-g-sib--tlac-gsib_tlacpy)
- [11. Crypto-assets](#11-crypto-assets-crypto_assetspy)
- [12. Credit Risk Advanced](#12-credit-risk-advanced-credit_risk_advancedpy)
- [13. Securitization Tests](#13-securitization-tests-securitization_testspy)
- [14. Step-in Risk](#14-step-in-risk-step_in_riskpy)
- [15. Pillar 3 Disclosures](#15-pillar-3-disclosures-pillar3py)
- [16. Stress Testing](#16-stress-testing-stress_testingpy)
- [17. Simplified Market Risk](#17-simplified-market-risk-simplified_sa_mrpy)
- [18. Total Capital Integration](#18-total-capital-integration-total_capitalpy)

### Basel II (2004 Framework + Basel 2.5 Enhancements)
- [19. Basel II Credit Risk SA](#19-basel-ii-credit-risk-sa-basel2credit_risk_sapy)
- [20. Basel II Credit Risk IRB](#20-basel-ii-credit-risk-irb-basel2credit_risk_irbpy)
- [21. Basel II Counterparty Credit Risk](#21-basel-ii-counterparty-credit-risk-basel2counterparty_credit_riskpy)
- [22. Basel II Operational Risk](#22-basel-ii-operational-risk-basel2operational_riskpy)
- [23. Basel II Market Risk](#23-basel-ii-market-risk-basel2market_riskpy)
- [24. Basel 2.5 Market Risk Enhancements](#24-basel-25-market-risk-enhancements-basel2basel25_market_riskpy)
- [25. Basel II Securitization](#25-basel-ii-securitization-basel2securitizationpy)
- [26. Basel II Credit Risk Mitigation](#26-basel-ii-credit-risk-mitigation-basel2credit_risk_mitigationpy)
- [27. Basel II Equity Banking Book](#27-basel-ii-equity-banking-book-basel2equity_banking_bookpy)

---

## 1. Core Credit Risk (rwa_calc.py)

### `calculate_sa_rwa()`
**SA-CR (Standardised Approach) RWA calculation**

| Input | Type | Description |
|-------|------|-------------|
| `ead` | float | Exposure at Default |
| `exposure_class` | str | "sovereign", "bank", "corporate", "retail", "residential_re", "commercial_re", "defaulted", "equity" |
| `rating` | str | External rating (e.g., "AAA", "BBB", "unrated") |
| **Kwargs by class:** |
| *bank:* `approach` | str | "ECRA" or "SCRA" |
| *bank:* `scra_grade` | str | "A", "B", or "C" |
| *bank:* `short_term` | bool | Maturity <= 3 months |
| *corporate:* `is_sme` | bool | SME supporting factor |
| *retail:* `retail_type` | str | "regulatory_retail", "transactor" |
| *real_estate:* `ltv` | float | Loan-to-Value ratio (0.75 = 75%) |
| *real_estate:* `income_producing` | bool | Income-producing property |

| Output | Type | Description |
|--------|------|-------------|
| `approach` | str | "SA-CR" |
| `ead` | float | Input EAD |
| `exposure_class` | str | Input exposure class |
| `rating` | str | Input rating |
| `risk_weight_pct` | float | Risk weight (%) |
| `rwa` | float | Risk-weighted assets |
| `capital_requirement_k` | float | K = RW / 12.5 |

---

### `calculate_rwa()` / `calculate_airb_rwa()`
**F-IRB / A-IRB RWA calculation**

| Input | Type | Description |
|-------|------|-------------|
| `ead` | float | Exposure at Default |
| `pd` | float | Probability of Default (0.01 = 1%) |
| `lgd` | float | Loss Given Default (0.45 = 45%) |
| `maturity` | float | Effective maturity in years (default: 2.5) |
| `asset_class` | str | "corporate", "retail_mortgage", "retail_revolving", "retail_other" |
| *A-IRB only:* `lgd_downturn` | float | Downturn LGD if different |

| Output | Type | Description |
|--------|------|-------------|
| `approach` | str | "IRB-F" or "A-IRB" |
| `ead` | float | Input EAD |
| `pd` | float | Input PD (floored at 0.03%) |
| `lgd` | float | Input LGD |
| `maturity` | float | Input maturity |
| `correlation` | float | Asset correlation R |
| `capital_requirement_k` | float | Capital requirement K |
| `risk_weight_pct` | float | Risk weight (%) |
| `rwa` | float | Risk-weighted assets |
| `expected_loss` | float | PD * LGD * EAD |

---

### `calculate_sec_sa_rwa()`
**SEC-SA (Securitization Standardised Approach)**

| Input | Type | Description |
|-------|------|-------------|
| `ead` | float | Tranche exposure |
| `attachment` | float | Attachment point (0.05 = 5%) |
| `detachment` | float | Detachment point (0.15 = 15%) |
| `ksa` | float | Pool capital charge under SA (default: 0.08) |
| `n` | int | Effective number of exposures (default: 25) |
| `lgd` | float | Pool average LGD (default: 0.50) |
| `w` | float | Delinquent ratio (default: 0) |
| `is_sts` | bool | STS securitization (lower floor) |

| Output | Type | Description |
|--------|------|-------------|
| `approach` | str | "SEC-SA" |
| `ead` | float | Tranche EAD |
| `attachment` | float | Attachment point |
| `detachment` | float | Detachment point |
| `thickness` | float | D - A |
| `ksa` | float | Pool Ksa |
| `risk_weight_pct` | float | Risk weight (15%-1250%) |
| `rwa` | float | Risk-weighted assets |

---

### `calculate_sec_irba_rwa()`
**SEC-IRBA (Securitization IRB Approach)**

| Input | Type | Description |
|-------|------|-------------|
| `ead` | float | Tranche exposure |
| `attachment` | float | Attachment point |
| `detachment` | float | Detachment point |
| `kirb` | float | Pool capital charge under IRB (default: 0.06) |
| `n` | int | Effective number of exposures |
| `lgd` | float | Pool average LGD |
| `is_sts` | bool | STS securitization |

| Output | Type | Description |
|--------|------|-------------|
| `approach` | str | "SEC-IRBA" |
| `kirb` | float | Pool Kirb |
| `risk_weight_pct` | float | Risk weight |
| `rwa` | float | Risk-weighted assets |

---

### `calculate_erba_rwa()`
**ERBA (External Ratings-Based Approach)**

| Input | Type | Description |
|-------|------|-------------|
| `ead` | float | Exposure at Default |
| `rating` | str | External rating |
| `seniority` | str | "senior" or "non_senior" |
| `maturity` | float | Effective maturity in years |

| Output | Type | Description |
|--------|------|-------------|
| `approach` | str | "ERBA" |
| `rating` | str | Input rating |
| `seniority` | str | Input seniority |
| `risk_weight_pct` | float | Risk weight (15%-1250%) |
| `rwa` | float | Risk-weighted assets |

---

### `calculate_iaa_rwa()`
**IAA (Internal Assessment Approach) for ABCP**

| Input | Type | Description |
|-------|------|-------------|
| `ead` | float | Exposure at Default |
| `internal_rating` | str | Bank's internal rating (AAA to below_BBB-) |
| `is_liquidity_facility` | bool | Liquidity facility (lower RW) |
| `facility_maturity` | float | Maturity for liquidity facilities |

| Output | Type | Description |
|--------|------|-------------|
| `approach` | str | "IAA" |
| `internal_rating` | str | Input rating |
| `risk_weight_pct` | float | Risk weight (15%-1250%) |
| `rwa` | float | Risk-weighted assets |

---

### `get_rating_from_pd()`
**PD to Rating Mapping - Convert PD values to external ratings**

| Input | Type | Description |
|-------|------|-------------|
| `pd` | float | Probability of Default (e.g., 0.02 for 2%) |

| Output | Type | Description |
|--------|------|-------------|
| (return) | str | Closest external rating (e.g., "BB" for PD ~2%) |

**Mapping Reference:**
| PD Range | Rating |
|----------|--------|
| ≤0.01% | AAA |
| 0.02% | AA+ |
| 0.03% | AA |
| 0.05% | AA- |
| 0.07% | A+ |
| 0.09% | A |
| 0.15% | A- |
| 0.25% | BBB+ |
| 0.40% | BBB |
| 0.75% | BBB- |
| 1.25% | BB+ |
| 2.00% | BB |
| 3.50% | BB- |
| 5.50% | B+ |
| 9.00% | B |
| 14.00% | B- |
| 20.00% | CCC+ |
| 27.00% | CCC |
| 35.00% | CCC- |
| ≥50.00% | below_CCC- |

---

### `get_pd_range_for_rating()`
**Get PD boundaries for a rating**

| Input | Type | Description |
|-------|------|-------------|
| `rating` | str | External credit rating |

| Output | Type | Description |
|--------|------|-------------|
| (return) | tuple[float, float] | (lower_bound, upper_bound) PD range |

---

### `calculate_rwa_from_pd()`
**Unified RWA calculation from PD/LGD - routes to any methodology**

| Input | Type | Description |
|-------|------|-------------|
| `ead` | float | Exposure at Default |
| `pd` | float | Probability of Default (e.g., 0.02 for 2%) |
| `lgd` | float | Loss Given Default (default: 0.45) |
| `approach` | str | "IRB-F", "A-IRB", "SA-CR", "ERBA", or "IAA" |
| `maturity` | float | Effective maturity in years (default: 2.5) |
| `exposure_class` | str | For SA-CR: "sovereign", "bank", "corporate", etc. |
| `asset_class` | str | For IRB: "corporate", "retail_mortgage", etc. |
| **Kwargs by approach:** |
| *SA-CR:* `is_sme` | bool | SME supporting factor |
| *SA-CR:* `short_term` | bool | Short-term exposure |
| *SA-CR:* `ltv` | float | Loan-to-Value ratio |
| *ERBA:* `seniority` | str | "senior" or "non_senior" |
| *IAA:* `is_liquidity_facility` | bool | Liquidity facility treatment |
| *A-IRB:* `lgd_downturn` | float | Downturn LGD |

| Output | Type | Description |
|--------|------|-------------|
| `approach` | str | Approach used |
| `ead` | float | Input EAD |
| `derived_rating` | str | Rating derived from PD |
| `pd_used` | float | PD used (for rating-based approaches) |
| `risk_weight_pct` | float | Risk weight (%) |
| `rwa` | float | Risk-weighted assets |
| `capital_requirement_k` | float | Capital requirement K |

---

### `calculate_securitization_rwa_from_pd()`
**Securitization RWA using PD/LGD pool data**

| Input | Type | Description |
|-------|------|-------------|
| `ead` | float | Tranche exposure |
| `attachment` | float | Attachment point (e.g., 0.05 for 5%) |
| `detachment` | float | Detachment point (e.g., 0.15 for 15%) |
| `pool_exposures` | list[dict] | Underlying pool, each with: |
| | `ead` | float | Exposure amount |
| | `pd` | float | Probability of Default |
| | `lgd` | float | Loss Given Default (optional, default: 0.45) |
| | `maturity` | float | Maturity (optional, default: 2.5) |
| | `exposure_class` | str | For SA: exposure class |
| | `asset_class` | str | For IRB: asset class |
| `approach` | str | "SEC-SA" or "SEC-IRBA" |
| `n` | int | Effective N (if None, calculated from pool) |
| `lgd` | float | Pool average LGD for supervisory formula |
| `is_sts` | bool | STS securitization |
| `w` | float | Delinquent ratio (SEC-SA only) |

| Output | Type | Description |
|--------|------|-------------|
| `approach` | str | "SEC-SA" or "SEC-IRBA" |
| `ead` | float | Tranche EAD |
| `attachment` | float | Attachment point |
| `detachment` | float | Detachment point |
| `ksa` or `kirb` | float | Pool capital charge (calculated) |
| `risk_weight_pct` | float | Tranche risk weight |
| `rwa` | float | Risk-weighted assets |
| `pool_statistics` | dict | Pool summary: |
| | `total_ead` | float | Total pool EAD |
| | `n_exposures` | int | Number of exposures |
| | `effective_n` | int | Effective N (Herfindahl) |
| | `avg_pd` | float | Weighted average PD |
| | `avg_lgd` | float | Weighted average LGD |

---

### `compare_all_approaches_from_pd()`
**Compare all credit risk approaches using PD/LGD**

| Input | Type | Description |
|-------|------|-------------|
| `ead` | float | Exposure at Default |
| `pd` | float | Probability of Default |
| `lgd` | float | Loss Given Default (default: 0.45) |
| `maturity` | float | Effective maturity (default: 2.5) |
| `exposure_class` | str | SA exposure class |
| `seniority` | str | ERBA seniority |

| Output | Type | Description |
|--------|------|-------------|
| `ead` | float | Input EAD |
| `pd` | float | Input PD |
| `lgd` | float | Input LGD |
| `derived_rating` | str | Rating derived from PD |
| `sa` | dict | SA-CR result |
| `irb_f` | dict | IRB-F result |
| `airb` | dict | A-IRB result |
| `erba` | dict | ERBA result |
| `most_conservative` | str | Approach with highest RWA |
| `least_conservative` | str | Approach with lowest RWA |
| `ranking` | list | Approaches ranked by RWA |
| `rwa_range` | tuple | (min RWA, max RWA) |

---

### `calculate_batch_rwa_from_pd()`
**Batch RWA calculation for portfolio with PD/LGD data**

| Input | Type | Description |
|-------|------|-------------|
| `exposures` | list[dict] | Portfolio exposures, each with: |
| | `ead` | float | Exposure at Default |
| | `pd` | float | Probability of Default |
| | `lgd` | float | Loss Given Default (optional) |
| | `maturity` | float | Maturity (optional) |
| | `exposure_class` | str | For SA-CR (optional) |
| | `asset_class` | str | For IRB (optional) |
| `approach` | str | "IRB-F", "A-IRB", "SA-CR", "ERBA", or "IAA" |

| Output | Type | Description |
|--------|------|-------------|
| `approach` | str | Approach used |
| `total_ead` | float | Sum of all EADs |
| `total_rwa` | float | Sum of all RWAs |
| `total_expected_loss` | float | Sum of EL |
| `average_risk_weight_pct` | float | Portfolio average RW |
| `exposure_count` | int | Number of exposures |
| `exposures` | list | Individual results |

---

## 2. Counterparty Credit Risk (counterparty_risk.py)

### `calculate_sa_ccr_ead()`
**SA-CCR EAD calculation for derivatives**

| Input | Type | Description |
|-------|------|-------------|
| `trades` | list[dict] | List of trades, each with: |
| | `notional` | float | Trade notional |
| | `asset_class` | str | "IR", "FX", "CR_BBB", "EQ_SINGLE", "COM_OIL_GAS", etc. |
| | `maturity` | float | Time to maturity (years) |
| | `mtm` | float | Mark-to-market value |
| | `delta` | float | Delta adjustment (+1/-1 or option delta) |
| `collateral_held` | float | Collateral received |
| `collateral_posted` | float | Collateral posted |
| `is_margined` | bool | Subject to margin agreement |
| `threshold` | float | Margin threshold (TH) |
| `mta` | float | Minimum transfer amount |
| `nica` | float | Net independent collateral |
| `alpha` | float | Alpha factor (default: 1.4) |

| Output | Type | Description |
|--------|------|-------------|
| `approach` | str | "SA-CCR" |
| `replacement_cost` | float | RC component |
| `pfe` | float | Potential Future Exposure |
| `addon_aggregate` | float | Total add-on |
| `addons_by_class` | dict | Add-ons by asset class |
| `multiplier` | float | PFE multiplier |
| `ead` | float | EAD = alpha * (RC + PFE) |
| `total_mtm` | float | Portfolio MTM |

---

### `calculate_ba_cva()`
**BA-CVA (Basic Approach for CVA)**

| Input | Type | Description |
|-------|------|-------------|
| `counterparties` | list[dict] | List of counterparties, each with: |
| | `ead` | float | Exposure to counterparty |
| | `rating` | str | Counterparty rating |
| | `maturity` | float | Effective maturity |

| Output | Type | Description |
|--------|------|-------------|
| `approach` | str | "BA-CVA" |
| `k_cva` | float | CVA capital charge |
| `rwa` | float | K_CVA * 12.5 |
| `counterparties` | list | Per-counterparty breakdown |

---

### `calculate_sa_cva()`
**SA-CVA (Standardised Approach for CVA)**

| Input | Type | Description |
|-------|------|-------------|
| `counterparties` | list[dict] | Each with: ead, sector, rating, maturity |
| `hedges` | list[dict] | CVA hedges: notional, effectiveness |

| Output | Type | Description |
|--------|------|-------------|
| `approach` | str | "SA-CVA" |
| `k_cva_gross` | float | Gross CVA capital |
| `hedge_benefit` | float | Hedge benefit |
| `k_cva` | float | Net CVA capital |
| `rwa` | float | CVA RWA |
| `bucket_capitals` | dict | By sector |

---

## 3. Market Risk (market_risk.py)

### `calculate_frtb_sa()`
**FRTB Standardised Approach (SbM + DRC + RRAO)**

| Input | Type | Description |
|-------|------|-------------|
| `delta_positions` | dict | Delta positions by risk class: |
| | key | str | "GIRR", "CSR", "EQ", "FX", "COM" |
| | value | list[dict] | Positions with: bucket, sensitivity, risk_weight |
| `vega_positions` | dict | Vega positions (same structure) |
| `curvature_positions` | dict | Curvature positions |
| `drc_positions` | list[dict] | DRC positions: obligor, notional, rating, seniority, is_long |
| `rrao_positions` | list[dict] | RRAO positions: notional, is_exotic, has_other_residual_risk |

| Output | Type | Description |
|--------|------|-------------|
| `approach` | str | "FRTB-SA" |
| `sbm_capital` | float | Total SbM capital |
| `sbm_by_risk_class` | dict | SbM breakdown |
| `drc_capital` | float | Default Risk Charge |
| `rrao_capital` | float | Residual Risk Add-On |
| `total_capital` | float | Total market risk capital |
| `total_rwa` | float | Capital * 12.5 |

---

### `calculate_drc_charge()`
**Default Risk Charge**

| Input | Type | Description |
|-------|------|-------------|
| `positions` | list[dict] | Each with: |
| | `obligor` | str | Obligor identifier |
| | `notional` | float | Position notional |
| | `rating` | str | Credit rating |
| | `seniority` | str | "senior", "subordinated", "equity" |
| | `sector` | str | Industry sector |
| | `is_long` | bool | Long or short |

| Output | Type | Description |
|--------|------|-------------|
| `approach` | str | "DRC" |
| `total_drc` | float | Total DRC capital |
| `rwa` | float | DRC * 12.5 |
| `obligors` | dict | By-obligor breakdown |

---

## 4. Operational Risk (operational_risk.py)

### `calculate_sma_capital()`
**SMA (Standardised Measurement Approach)**

| Input | Type | Description |
|-------|------|-------------|
| `bi` | float | Business Indicator (3-year average) |
| `average_annual_loss` | float | Average annual operational loss (10-year) |
| `use_ilm` | bool | Use Internal Loss Multiplier |
| **OR provide components:** |
| `ildc` | float | Interest, Leasing, Dividend Component |
| `sc` | float | Services Component |
| `fc` | float | Financial Component |
| **OR provide detailed P&L:** |
| `interest_income` | float | Gross interest income |
| `interest_expense` | float | Gross interest expense |
| `interest_earning_assets` | float | Average IEA |
| `fee_income` | float | Fee income |
| `fee_expense` | float | Fee expense |
| `trading_book_pnl` | float | Trading P&L |
| `banking_book_pnl` | float | Banking book P&L |

| Output | Type | Description |
|--------|------|-------------|
| `approach` | str | "SMA" |
| `business_indicator` | float | BI value |
| `bic` | float | Business Indicator Component |
| `loss_component` | float | LC = 15 * avg loss |
| `ilm` | float | Internal Loss Multiplier |
| `bucket` | int | 1, 2, or 3 |
| `k_sma` | float | SMA capital = BIC * ILM |
| `rwa` | float | K_SMA * 12.5 |

---

## 5. Capital Framework (capital_framework.py)

### `calculate_output_floor()`
**Output Floor calculation (72.5%)**

| Input | Type | Description |
|-------|------|-------------|
| `rwa_irb` | float | RWA under IRB approach |
| `rwa_standardised` | float | RWA under Standardised approach |
| `year` | int | Year (2023-2028 for transition) |

| Output | Type | Description |
|--------|------|-------------|
| `rwa_irb` | float | Input IRB RWA |
| `rwa_standardised` | float | Input SA RWA |
| `floor_percentage` | float | 0.50-0.725 based on year |
| `floor_rwa` | float | floor% * SA RWA |
| `floored_rwa` | float | max(IRB, floor) |
| `floor_addon` | float | Additional RWA if floor binding |
| `floor_is_binding` | bool | Whether floor binds |

---

### `calculate_leverage_ratio()`
**Leverage Ratio (3% minimum)**

| Input | Type | Description |
|-------|------|-------------|
| `tier1_capital` | float | Tier 1 capital |
| `on_balance_sheet` | float | On-BS exposures |
| `derivatives_exposure` | float | Derivatives (SA-CCR) |
| `sft_exposure` | float | Securities financing |
| `off_balance_sheet` | float | Off-BS after CCF |
| `is_gsib` | bool | G-SIB bank |
| `gsib_buffer_pct` | float | G-SIB buffer rate |

| Output | Type | Description |
|--------|------|-------------|
| `tier1_capital` | float | Input capital |
| `total_exposure` | float | Total exposure measure |
| `leverage_ratio` | float | T1 / Exposure |
| `leverage_ratio_pct` | float | As percentage |
| `minimum_requirement` | float | 3% + G-SIB buffer |
| `is_compliant` | bool | Meets requirement |
| `buffer` | float | Excess over minimum |

---

### `calculate_large_exposure()`
**Large Exposures Framework (25% limit)**

| Input | Type | Description |
|-------|------|-------------|
| `exposure_value` | float | Total exposure to counterparty |
| `tier1_capital` | float | Bank's Tier 1 capital |
| `counterparty_type` | str | "corporate", "bank", "sovereign" |
| `is_gsib_counterparty` | bool | Counterparty is G-SIB |
| `bank_is_gsib` | bool | Bank is G-SIB |

| Output | Type | Description |
|--------|------|-------------|
| `exposure_pct` | float | Exposure as % of T1 |
| `is_large_exposure` | bool | >= 10% threshold |
| `limit` | float | 25% (15% for G-SIB to G-SIB) |
| `exceeds_limit` | bool | Above limit |
| `headroom_pct` | float | Available capacity |
| `max_exposure` | float | T1 * limit |

---

### `calculate_exposure_with_crm()`
**Credit Risk Mitigation**

| Input | Type | Description |
|-------|------|-------------|
| `exposure_value` | float | Original exposure |
| `collateral` | list[dict] | Each with: type, value, rating, maturity, currency_mismatch |
| `guarantee_value` | float | Guarantee amount |
| `guarantor_rw` | float | Guarantor risk weight |
| `credit_derivative_value` | float | CD protection |
| `exposure_rw` | float | Original exposure RW |

| Output | Type | Description |
|--------|------|-------------|
| `original_exposure` | float | Input exposure |
| `total_collateral_adjusted` | float | After haircuts |
| `exposure_after_crm` | float | Net exposure |
| `original_rwa` | float | RWA before CRM |
| `rwa_after_crm` | float | RWA after CRM |
| `rwa_reduction` | float | Benefit from CRM |

---

### `calculate_ead_off_balance_sheet()`
**Credit Conversion Factors (CCF)**

| Input | Type | Description |
|-------|------|-------------|
| `commitment_amount` | float | Total commitment |
| `commitment_type` | str | "commitment_over_1y", "direct_credit_substitute", etc. |
| `drawn_amount` | float | Amount already drawn |
| `approach` | str | "SA" or "IRB" |

| Output | Type | Description |
|--------|------|-------------|
| `commitment_amount` | float | Total commitment |
| `undrawn_amount` | float | Undrawn portion |
| `ccf` | float | Credit conversion factor |
| `ead` | float | drawn + CCF * undrawn |

---

## 6. Specialized Lending (specialized_lending.py)

### `calculate_slotting_rwa()` / `calculate_project_finance_rwa()` / `calculate_ipre_rwa()` / `calculate_hvcre_rwa()`
**Slotting Criteria Approach**

| Input | Type | Description |
|-------|------|-------------|
| `ead` | float | Exposure at Default |
| `category` | SlottingCategory | STRONG, GOOD, SATISFACTORY, WEAK, DEFAULT |
| `exposure_type` | str | "standard" or "hvcre" |
| **Project Finance:** |
| `phase` | str | "pre_operational" or "operational" |
| `dscr` | float | Debt Service Coverage Ratio |
| `ltv` | float | Loan-to-Value |
| `country_risk` | str | "low", "moderate", "high" |
| `sponsor_rating` | str | "strong", "good", "satisfactory", "weak" |
| **IPRE:** |
| `property_type` | str | "office", "retail", "industrial", "multifamily" |
| `occupancy_rate` | float | Current occupancy |
| `location_quality` | str | "prime", "good", "secondary", "tertiary" |
| **HVCRE:** |
| `pre_sales_rate` | float | Units pre-sold |
| `sponsor_equity` | float | Equity contribution |

| Output | Type | Description |
|--------|------|-------------|
| `approach` | str | "Slotting" |
| `category` | str | Slotting category |
| `risk_weight_pct` | float | 70%/90%/115%/250% (standard) or 95%/120%/140%/250% (HVCRE) |
| `rwa` | float | Risk-weighted assets |
| `sub_type` | str | "project_finance", "ipre", "hvcre" |

---

## 7. Liquidity (liquidity.py)

### `calculate_lcr()`
**Liquidity Coverage Ratio**

| Input | Type | Description |
|-------|------|-------------|
| `hqla` | dict | High-quality liquid assets: |
| | `level1` | float | Level 1 (cash, reserves) |
| | `level2a` | float | Level 2A (gov bonds) |
| | `level2b` | float | Level 2B (corp bonds) |
| `outflows` | dict | Cash outflows by type |
| `inflows` | dict | Cash inflows by type |

| Output | Type | Description |
|--------|------|-------------|
| `total_hqla` | float | After haircuts |
| `total_outflows` | float | Stressed outflows |
| `total_inflows` | float | Capped inflows |
| `net_outflows` | float | Outflows - inflows |
| `lcr` | float | HQLA / Net outflows |
| `lcr_pct` | float | LCR as percentage |
| `compliant` | bool | >= 100% |

---

### `calculate_nsfr()`
**Net Stable Funding Ratio**

| Input | Type | Description |
|-------|------|-------------|
| `asf_items` | list[dict] | Available stable funding: amount, category |
| `rsf_items` | list[dict] | Required stable funding: amount, category |

| Output | Type | Description |
|--------|------|-------------|
| `total_asf` | float | Available stable funding |
| `total_rsf` | float | Required stable funding |
| `nsfr` | float | ASF / RSF |
| `nsfr_pct` | float | NSFR as percentage |
| `compliant` | bool | >= 100% |

---

## 8. IRRBB (irrbb.py)

### `calculate_eve_all_scenarios()`
**Economic Value of Equity sensitivity**

| Input | Type | Description |
|-------|------|-------------|
| `cash_flows` | list[dict] | Each with: amount, time, is_asset |
| `current_rates` | dict | Current yield curve by tenor |
| `tier1_capital` | float | For outlier test |

| Output | Type | Description |
|--------|------|-------------|
| `eve_base` | float | Base EVE |
| `eve_by_scenario` | dict | EVE under 6 scenarios |
| `delta_eve` | dict | Change from base |
| `worst_scenario` | str | Most adverse scenario |
| `max_delta` | float | Maximum EVE change |
| `outlier_ratio` | float | Max delta / T1 |
| `is_outlier` | bool | > 15% of T1 |

---

### `calculate_nii_sensitivity()`
**Net Interest Income sensitivity**

| Input | Type | Description |
|-------|------|-------------|
| `repricing_gaps` | dict | Gap by time bucket |
| `rate_shock` | float | Rate shock (bps) |
| `horizon` | int | Months (default: 12) |

| Output | Type | Description |
|--------|------|-------------|
| `nii_impact` | float | NII change |
| `by_bucket` | dict | Impact per bucket |

---

## 9. Equity & CCP (equity_ccp.py)

### `calculate_equity_rwa()`
**Equity exposures under banking book**

| Input | Type | Description |
|-------|------|-------------|
| `exposure_value` | float | Fair value of equity |
| `approach` | str | "simple", "pd_lgd" |
| `equity_type` | str | "listed", "unlisted", "speculative" |
| `pd` | float | For PD/LGD approach |
| `lgd` | float | For PD/LGD approach |

| Output | Type | Description |
|--------|------|-------------|
| `approach` | str | "Simple RW" or "PD/LGD" |
| `risk_weight_pct` | float | 100%/250%/300%/400% |
| `rwa` | float | Risk-weighted assets |

---

### `calculate_ccp_exposure()`
**CCP exposures**

| Input | Type | Description |
|-------|------|-------------|
| `trade_exposure` | float | EAD for trades |
| `default_fund_contribution` | float | DF contribution |
| `is_qccp` | bool | Qualifying CCP |
| `ccp_hypothetical_capital` | float | CCP's K_CCP |
| `total_default_fund` | float | Total DF |

| Output | Type | Description |
|--------|------|-------------|
| `trade_rwa` | float | 2% RW for QCCP trades |
| `df_rwa` | float | Default fund RWA |
| `total_rwa` | float | Combined RWA |

---

## 10. G-SIB & TLAC (gsib_tlac.py)

### `calculate_gsib_score()`
**G-SIB scoring methodology**

| Input | Type | Description |
|-------|------|-------------|
| `indicators` | dict | 12 indicators across 5 categories: |
| | `size.total_exposures` | float | Total exposures |
| | `interconnectedness.intra_financial` | float | Intra-financial assets |
| | `interconnectedness.intra_financial_liabilities` | float | Intra-financial liabilities |
| | `interconnectedness.securities_outstanding` | float | Securities outstanding |
| | `substitutability.payments_activity` | float | Payments cleared |
| | `substitutability.assets_under_custody` | float | AUC |
| | `substitutability.underwriting_activity` | float | Debt + equity underwritten |
| | `complexity.otc_derivatives` | float | OTC notional |
| | `complexity.trading_securities` | float | Trading + AFS securities |
| | `complexity.level3_assets` | float | Level 3 assets |
| | `cross_jurisdictional.cross_jurisdictional_claims` | float | Foreign claims |
| | `cross_jurisdictional.cross_jurisdictional_liabilities` | float | Foreign liabilities |
| `denominators` | dict | Global denominators for each indicator |

| Output | Type | Description |
|--------|------|-------------|
| `total_score` | float | G-SIB score (basis points) |
| `category_scores` | dict | Score by category |
| `bucket` | int | 1-5 (or 0 if not G-SIB) |
| `buffer` | float | Additional buffer (1%-3.5%) |
| `is_gsib` | bool | Score >= 130 bps |

---

### `calculate_tlac_requirement()`
**TLAC/MREL requirements**

| Input | Type | Description |
|-------|------|-------------|
| `rwa` | float | Total RWA |
| `leverage_exposure` | float | Leverage exposure measure |
| `gsib_buffer` | float | G-SIB buffer rate |

| Output | Type | Description |
|--------|------|-------------|
| `tlac_rwa_requirement` | float | 18% of RWA + buffers |
| `tlac_leverage_requirement` | float | 6.75% of leverage exposure |
| `binding_constraint` | str | "rwa" or "leverage" |
| `tlac_required` | float | Higher of two |

---

## 11. Crypto-assets (crypto_assets.py)

### `calculate_crypto_rwa()`
**Crypto-asset capital requirements**

| Input | Type | Description |
|-------|------|-------------|
| `exposure` | float | Exposure amount |
| `group` | str | "1a", "1b", "2a", "2b" |
| `underlying_rw` | float | For Group 1a (underlying asset RW) |
| `redemption_risk` | float | For Group 1b (0-2.5% add-on) |
| `has_hedging` | bool | For Group 2a (hedging recognition) |

| Output | Type | Description |
|--------|------|-------------|
| `group` | str | Crypto group classification |
| `base_rw` | float | Base risk weight |
| `add_on` | float | Infrastructure/redemption add-on |
| `effective_rw` | float | Total risk weight |
| `rwa` | float | Risk-weighted assets |

---

### `check_crypto_exposure_limits()`
**Group 2 exposure limits**

| Input | Type | Description |
|-------|------|-------------|
| `group2_exposure` | float | Total Group 2 exposure |
| `group2b_exposure` | float | Group 2b exposure |
| `tier1_capital` | float | Tier 1 capital |

| Output | Type | Description |
|--------|------|-------------|
| `group2_ratio` | float | Group 2 / T1 |
| `group2b_ratio` | float | Group 2b / T1 |
| `group2_limit_breach` | bool | > 2% |
| `group2b_limit_breach` | bool | > 1% |

---

## 12. Credit Risk Advanced (credit_risk_advanced.py)

### `calculate_infrastructure_rwa()`
**Infrastructure Supporting Factor (0.75x)**

| Input | Type | Description |
|-------|------|-------------|
| `exposure` | InfrastructureExposure | Dataclass with: |
| | `ead` | float | Exposure at Default |
| | `pd` | float | Probability of Default |
| | `lgd` | float | Loss Given Default |
| | `maturity` | float | Effective maturity |
| | `is_operational` | bool | Operational vs construction |
| | `has_take_or_pay` | bool | Take-or-pay contract |
| | `has_regulated_revenue` | bool | Regulated revenue |
| | `meets_financial_criteria` | bool | Financial requirements met |

| Output | Type | Description |
|--------|------|-------------|
| `rwa_base` | float | RWA without ISF |
| `infrastructure_supporting_factor` | float | 0.75 if eligible |
| `rwa_with_isf` | float | RWA * 0.75 |
| `rwa_reduction` | float | Benefit from ISF |

---

### `calculate_dilution_risk_rwa()`
**Purchased Receivables - Dilution Risk**

| Input | Type | Description |
|-------|------|-------------|
| `receivable` | PurchasedReceivable | Dataclass with: |
| | `ead` | float | Receivable amount |
| | `pd_dilution` | float | Dilution PD |
| | `lgd_dilution` | float | Dilution LGD (typically 100%) |
| | `has_recourse_to_seller` | bool | Recourse available |
| | `recourse_amount` | float | Recourse value |

| Output | Type | Description |
|--------|------|-------------|
| `rwa_dilution` | float | Dilution risk RWA |
| `lgd_dilution_adjusted` | float | LGD after recourse |

---

### `calculate_double_default_rwa()`
**Double Default Framework**

| Input | Type | Description |
|-------|------|-------------|
| `exposure` | GuaranteedExposure | Dataclass with: |
| | `ead` | float | Exposure at Default |
| | `pd_obligor` | float | Obligor PD |
| | `pd_guarantor` | float | Guarantor PD |
| | `lgd` | float | Loss Given Default |
| | `guarantor_type` | str | "sovereign", "bank", "corporate" |

| Output | Type | Description |
|--------|------|-------------|
| `pd_double_default` | float | Joint default probability |
| `rwa_double_default` | float | RWA with DD treatment |
| `rwa_unguaranteed` | float | RWA without guarantee |
| `reduction_percent` | float | RWA benefit |

---

## 13. Securitization Tests (securitization_tests.py)

### `evaluate_stc_compliance()`
**STC Criteria Checker (16 criteria)**

| Input | Type | Description |
|-------|------|-------------|
| `assessment` | STCAssessment | With criteria_met dict for: |
| | S1-S6 | bool | Simplicity criteria |
| | T1-T4 | bool | Transparency criteria |
| | C1-C6 | bool | Comparability criteria |

| Output | Type | Description |
|--------|------|-------------|
| `is_stc_compliant` | bool | All 16 criteria met |
| `criteria_met_count` | int | Number met |
| `category_results` | dict | By category |
| `failed_criteria` | list | Failed criteria details |
| `rwa_floor_benefit` | float | 10% vs 15% floor |

---

### `perform_srt_quantitative_test()`
**Significant Risk Transfer Test**

| Input | Type | Description |
|-------|------|-------------|
| `assessment` | SRTAssessment | With: |
| | `total_pool_amount` | float | Pool size |
| | `pool_rwa_if_not_securitized` | float | RWA if held |
| | `tranches` | list | Tranche details |
| `pd_pool` | float | Pool PD |
| `lgd_pool` | float | Pool LGD |

| Output | Type | Description |
|--------|------|-------------|
| `risk_transfer_ratio` | float | % risk transferred |
| `srt_achieved` | bool | >= 50% transfer |
| `capital_relief_available` | bool | Can deconsolidate |
| `estimated_capital_relief` | float | Capital saved |

---

## 14. Step-in Risk (step_in_risk.py)

### `assess_step_in_indicators()`
**Step-in Risk Assessment (BCBS 398)**

| Input | Type | Description |
|-------|------|-------------|
| `entity` | UnconsolidatedEntity | With: |
| | `entity_type` | EntityType | SPV, MMF, fund, etc. |
| | `total_assets` | float | Entity assets |
| | `is_sponsored` | bool | Bank sponsors entity |
| | `uses_bank_name` | bool | Name association |
| | `past_support_provided` | bool | Historical support |
| `has_implicit_support_expectation` | bool | Market expects support |
| `involvement_level` | float | 0-1 scale |
| `reputational_impact` | float | 0-1 scale |
| `investor_expectation_level` | float | 0-1 scale |

| Output | Type | Description |
|--------|------|-------------|
| `overall_score` | float | Weighted indicator score |
| `risk_level` | str | "high", "medium", "low" |
| `indicator_scores` | dict | Per-indicator scores |
| `notes` | list | Risk factors identified |

---

### `calculate_step_in_capital_impact()`
**Capital impact of step-in risk**

| Input | Type | Description |
|-------|------|-------------|
| `assessment` | StepInAssessment | From assess_step_in_indicators |
| `entity_rwa_if_consolidated` | float | RWA if fully consolidated |

| Output | Type | Description |
|--------|------|-------------|
| `treatment_approach` | str | "full_consolidation", "proportional", "monitoring" |
| `capital_charge_factor` | float | 1.0, 0.5, or 0.0 |
| `implied_rwa` | float | RWA charge |
| `capital_requirement` | float | 8% of implied RWA |

---

## 15. Pillar 3 Disclosures (pillar3.py)

### `generate_km1_template()`
**KM1 - Key Metrics**

| Input | Type | Description |
|-------|------|-------------|
| `cet1_capital` | float | CET1 capital |
| `at1_capital` | float | AT1 capital |
| `tier2_capital` | float | Tier 2 capital |
| `total_rwa` | float | Total RWA |
| `leverage_exposure` | float | Leverage exposure measure |
| `lcr` | float | LCR ratio |
| `nsfr` | float | NSFR ratio |

| Output | Type | Description |
|--------|------|-------------|
| `data` | dict | Structured disclosure data |
| | `available_capital` | dict | CET1, T1, Total |
| | `capital_ratios` | dict | CET1%, T1%, Total% |
| | `leverage_ratio` | dict | Exposure, ratio |
| | `liquidity_ratios` | dict | LCR, NSFR |

---

### `generate_ov1_template()`
**OV1 - Overview of RWA**

| Input | Type | Description |
|-------|------|-------------|
| `credit_risk_sa_rwa` | float | Credit RWA (SA) |
| `credit_risk_irb_rwa` | float | Credit RWA (IRB) |
| `ccr_rwa` | float | CCR RWA |
| `cva_rwa` | float | CVA RWA |
| `market_risk_rwa` | float | Market risk RWA |
| `operational_risk_rwa` | float | Op risk RWA |
| `floor_adjustment` | float | Output floor add-on |

| Output | Type | Description |
|--------|------|-------------|
| `data` | dict | RWA breakdown |
| | `risk_weighted_assets` | dict | By risk type |
| | `minimum_capital_requirements` | dict | 8% of each |
| | `breakdown_percentages` | dict | % composition |

---

## 16. Stress Testing (stress_testing.py)

### `run_integrated_stress_test()`
**Comprehensive stress test**

| Input | Type | Description |
|-------|------|-------------|
| `portfolio` | PortfolioData | Dataclass with: |
| | `credit_exposure` | float | Credit exposure |
| | `credit_rwa` | float | Credit RWA |
| | `average_pd` | float | Portfolio PD |
| | `average_lgd` | float | Portfolio LGD |
| | `market_var` | float | Market VaR |
| | `market_exposure` | float | Market exposure |
| | `operational_bir` | float | Business indicator |
| | `liquidity_hqla` | float | HQLA |
| | `liquidity_outflows` | float | Outflows |
| `scenario` | StressScenario | With macro paths |
| `cet1_capital` | float | Starting CET1 |
| `total_rwa` | float | Starting RWA |

| Output | Type | Description |
|--------|------|-------------|
| list[StressTestResult] | Each year with: |
| | `stressed_pd` | float | PD after stress |
| | `stressed_lgd` | float | LGD after stress |
| | `credit_losses` | float | Incremental credit losses |
| | `market_losses` | float | Market losses |
| | `operational_losses` | float | Op losses |
| | `total_losses` | float | All losses |
| | `capital_impact` | float | Cumulative capital hit |
| | `capital_ratio_impact` | float | CET1 ratio change |

---

### `generate_stress_test_report()`
**Stress test summary**

| Input | Type | Description |
|-------|------|-------------|
| `results` | list[StressTestResult] | From run_integrated_stress_test |
| `cet1_capital` | float | Starting capital |
| `total_rwa` | float | Starting RWA |
| `min_cet1_ratio` | float | Minimum requirement (4.5%) |

| Output | Type | Description |
|--------|------|-------------|
| `starting_position` | dict | Initial capital, RWA, ratio |
| `ending_position` | dict | Final capital, RWA, ratio |
| `cumulative_impact` | dict | Total losses by type |
| `buffer_analysis` | dict | Buffer vs requirement |
| `pass_fail` | str | "PASS" or "FAIL" |

---

## 17. Simplified Market Risk (simplified_sa_mr.py)

### `calculate_simplified_sa_capital()`
**Simplified SA for smaller banks**

| Input | Type | Description |
|-------|------|-------------|
| `positions` | list[SimplifiedPosition] | Each with: |
| | `instrument_type` | InstrumentType | IR, EQ, FX, COM, OPTION |
| | `notional` | float | Position notional |
| | `market_value` | float | Current value |
| | `residual_maturity` | float | Years to maturity |
| | `is_long` | bool | Long or short |
| | `delta` | float | For options |
| | `gamma` | float | For options |
| | `vega` | float | For options |

| Output | Type | Description |
|--------|------|-------------|
| `total_capital` | float | Total market risk capital |
| `interest_rate` | dict | IR charge breakdown |
| `equity` | dict | Equity charge breakdown |
| `foreign_exchange` | dict | FX charge breakdown |
| `commodity` | dict | Commodity charge |
| `options` | dict | Delta-plus charge |

---

### `check_simplified_sa_eligibility()`
**Eligibility check**

| Input | Type | Description |
|-------|------|-------------|
| `total_assets` | float | Total assets |
| `trading_book_assets` | float | Trading book size |
| `derivative_notional` | float | Derivatives notional |

| Output | Type | Description |
|--------|------|-------------|
| `is_eligible` | bool | Can use simplified SA |
| `trading_book_ratio` | float | TB / Total |
| `ratio_eligible` | bool | < 5% |
| `absolute_eligible` | bool | < EUR 50mn |

---

## 18. Total Capital Integration (total_capital.py)

### `calculate_total_rwa()`
**Integrated RWA calculation**

| Input | Type | Description |
|-------|------|-------------|
| `credit_exposures_sa` | list[dict] | SA credit exposures |
| `credit_exposures_irb` | list[dict] | IRB credit exposures |
| `use_airb` | bool | A-IRB vs F-IRB |
| `securitization_exposures` | list[dict] | Securitization tranches |
| `securitization_approach` | str | "SEC-SA", "SEC-IRBA", "ERBA" |
| `derivative_trades` | list[dict] | For SA-CCR |
| `cva_counterparties` | list[dict] | For CVA |
| `trading_positions` | dict | For FRTB-SA |
| `drc_positions` | list[dict] | For DRC |
| `business_indicator` | float | For SMA |
| `average_annual_loss` | float | For SMA |
| `apply_output_floor` | bool | Apply 72.5% floor |
| `floor_year` | int | Transition year |

| Output | Type | Description |
|--------|------|-------------|
| `credit_risk` | dict | SA and IRB RWA |
| `securitization` | dict | Securitization RWA |
| `counterparty_risk` | dict | CCR EAD and RWA |
| `cva_risk` | dict | CVA RWA |
| `market_risk` | dict | FRTB-SA RWA |
| `operational_risk` | dict | SMA RWA |
| `total_rwa_irb_based` | float | Total with IRB |
| `total_rwa_sa_based` | float | Total with SA |
| `output_floor` | dict | Floor details |
| `total_rwa` | float | Final floored RWA |

---

### `calculate_capital_ratios()`
**Capital ratios and compliance**

| Input | Type | Description |
|-------|------|-------------|
| `total_rwa` | float | Total RWA |
| `cet1_capital` | float | CET1 capital |
| `at1_capital` | float | AT1 capital |
| `tier2_capital` | float | Tier 2 capital |
| `countercyclical_buffer` | float | CCyB rate |
| `gsib_buffer` | float | G-SIB buffer rate |

| Output | Type | Description |
|--------|------|-------------|
| `cet1_ratio` | float | CET1 / RWA |
| `tier1_ratio` | float | T1 / RWA |
| `total_ratio` | float | Total / RWA |
| `requirements` | dict | Min requirements + buffers |
| `compliance` | dict | Pass/fail by ratio |
| `surplus` | dict | Excess capital |

---

# Basel II Framework (2004) + Basel 2.5 Enhancements (2009)

The Basel II functions are available in the `basel2/` package. Key differences from Basel III/IV:
- Operational Risk: BIA/TSA/AMA vs SMA
- Market Risk: VaR-based vs FRTB (ES-based)
- CCR: CEM/SM vs SA-CCR
- No output floor (72.5%)
- No leverage ratio requirement (3%)
- Different securitization hierarchy

---

## 19. Basel II Credit Risk SA (basel2/credit_risk_sa.py)

### `calculate_sa_rwa()`
**Basel II Standardised Approach RWA calculation**

| Input | Type | Description |
|-------|------|-------------|
| `ead` | float | Exposure at Default |
| `exposure_class` | str | "sovereign", "bank", "corporate", "retail", "residential_mortgage", "commercial_mortgage", "past_due", "other" |
| `rating` | str | External credit rating (default: "unrated") |
| **Kwargs by class:** |
| *bank:* `option` | int | 1 (sovereign-based) or 2 (bank rating-based) |
| *bank:* `short_term` | bool | Maturity <= 3 months |
| *bank:* `sovereign_rating` | str | For option 1 |
| *real_estate:* `fully_secured` | bool | Fully secured by property |
| *past_due:* `secured_by_residential` | bool | Residential security |
| *past_due:* `specific_provision_pct` | float | Provision as % |

| Output | Type | Description |
|--------|------|-------------|
| `approach` | str | "Basel II SA" |
| `ead` | float | Input EAD |
| `exposure_class` | str | Input class |
| `rating` | str | Input rating |
| `risk_weight_pct` | float | Risk weight (%) |
| `rwa` | float | Risk-weighted assets |
| `capital_requirement` | float | RWA * 8% |

**Basel II SA Risk Weight Tables:**

| Exposure Class | AAA-AA- | A+-A- | BBB+-BBB- | BB+-B- | Below B- | Unrated |
|---------------|---------|-------|-----------|--------|----------|---------|
| Sovereign | 0% | 20% | 50% | 100% | 150% | 100% |
| Bank (Opt 2) | 20% | 50% | 50% | 100% | 150% | 50% |
| Corporate | 20% | 50% | 100% | 100% | 150% | 100% |
| Retail | - | - | - | - | - | 75% |
| Residential RE | - | - | - | - | - | 35% |
| Commercial RE | - | - | - | - | - | 100% |

---

### `calculate_batch_sa_rwa()`
**Batch Basel II SA calculation**

| Input | Type | Description |
|-------|------|-------------|
| `exposures` | list[dict] | List of exposures, each with: ead, exposure_class, rating, and class-specific params |

| Output | Type | Description |
|--------|------|-------------|
| `approach` | str | "Basel II SA" |
| `total_ead` | float | Sum of EADs |
| `total_rwa` | float | Sum of RWAs |
| `average_risk_weight_pct` | float | Portfolio average RW |
| `total_capital_requirement` | float | Total capital |
| `exposures` | list | Individual results |

---

### `calculate_off_balance_sheet_ead()`
**Off-balance sheet EAD with Basel II CCFs**

| Input | Type | Description |
|-------|------|-------------|
| `notional` | float | Total commitment amount |
| `commitment_type` | str | See CCF table below |
| `drawn_amount` | float | Amount already drawn |

| Output | Type | Description |
|--------|------|-------------|
| `notional` | float | Total commitment |
| `drawn_amount` | float | Drawn portion |
| `undrawn_amount` | float | Undrawn portion |
| `commitment_type` | str | Input type |
| `ccf` | float | Credit conversion factor |
| `ead` | float | drawn + CCF * undrawn |

**Basel II Credit Conversion Factors:**

| Commitment Type | CCF |
|----------------|-----|
| direct_credit_substitute | 100% |
| transaction_related_contingent | 50% |
| short_term_self_liquidating | 20% |
| commitments_over_1y | 50% |
| commitments_up_to_1y | 20% |
| unconditionally_cancellable | 0% |
| nif_ruf | 50% |
| repo_style | 100% |

---

## 20. Basel II Credit Risk IRB (basel2/credit_risk_irb.py)

### `calculate_firb_rwa()`
**Foundation IRB RWA calculation**

Bank estimates PD; supervisor provides LGD, EAD, M.

| Input | Type | Description |
|-------|------|-------------|
| `ead` | float | Exposure at Default |
| `pd` | float | Bank-estimated PD (floored at 0.03%) |
| `seniority` | str | "senior" (45% LGD) or "subordinated" (75% LGD) |
| `collateral_type` | str | If secured: "receivables", "commercial_real_estate", etc. |
| `asset_class` | str | "corporate", "bank", "sovereign", "sme_corporate" |

| Output | Type | Description |
|--------|------|-------------|
| `approach` | str | "Basel II F-IRB" |
| `ead` | float | Input EAD |
| `pd` | float | Input PD (floored) |
| `lgd` | float | Supervisory LGD |
| `maturity` | float | Fixed 2.5 years |
| `correlation` | float | Asset correlation R |
| `capital_requirement_k` | float | Capital K |
| `risk_weight_pct` | float | K * 12.5 * 100 |
| `rwa` | float | K * 12.5 * EAD |
| `expected_loss` | float | PD * LGD * EAD |

**F-IRB Supervisory LGD:**

| Seniority/Collateral | LGD |
|---------------------|-----|
| Senior unsecured | 45% |
| Subordinated | 75% |
| Financial collateral | 0% (comprehensive approach) |
| Receivables | 35% |
| Commercial/Residential RE | 35% |
| Other physical | 40% |

---

### `calculate_airb_rwa()`
**Advanced IRB RWA calculation**

Bank estimates all parameters (PD, LGD, EAD, M).

| Input | Type | Description |
|-------|------|-------------|
| `ead` | float | Bank-estimated EAD |
| `pd` | float | Bank-estimated PD |
| `lgd` | float | Bank-estimated LGD (should be downturn) |
| `maturity` | float | Bank-estimated maturity (default: 2.5) |
| `asset_class` | str | "corporate", "retail_mortgage", "retail_revolving", "retail_other" |
| `lgd_downturn` | float | Explicit downturn LGD if different |

| Output | Type | Description |
|--------|------|-------------|
| `approach` | str | "Basel II A-IRB" |
| `ead` | float | Input EAD |
| `pd` | float | Input PD |
| `lgd` | float | LGD used |
| `maturity` | float | Input maturity |
| `correlation` | float | Asset correlation R |
| `capital_requirement_k` | float | Capital K |
| `risk_weight_pct` | float | Risk weight (%) |
| `rwa` | float | Risk-weighted assets |
| `expected_loss` | float | PD * LGD * EAD |

---

### `calculate_slotting_rwa()`
**Supervisory Slotting for specialized lending**

| Input | Type | Description |
|-------|------|-------------|
| `ead` | float | Exposure at Default |
| `category` | str | "Strong", "Good", "Satisfactory", "Weak", "Default" |
| `remaining_maturity` | float | Remaining maturity in years |

| Output | Type | Description |
|--------|------|-------------|
| `approach` | str | "Basel II Slotting" |
| `ead` | float | Input EAD |
| `category` | str | Input category |
| `remaining_maturity` | float | Input maturity |
| `term` | str | "short" (<2.5y) or "long" |
| `risk_weight_pct` | float | See table |
| `rwa` | float | Risk-weighted assets |
| `deduction` | float | Amount if default |
| `capital_requirement` | float | 8% of RWA |

**Slotting Risk Weights:**

| Category | < 2.5 years | >= 2.5 years |
|----------|-------------|--------------|
| Strong | 50% | 70% |
| Good | 70% | 90% |
| Satisfactory | 115% | 115% |
| Weak | 250% | 250% |
| Default | Deduction | Deduction |

---

### `compare_firb_vs_airb()`
**Compare F-IRB vs A-IRB for same exposure**

| Input | Type | Description |
|-------|------|-------------|
| `ead` | float | Exposure at Default |
| `pd` | float | Probability of Default |
| `airb_lgd` | float | Bank-estimated LGD for A-IRB |
| `airb_maturity` | float | Bank-estimated maturity for A-IRB |
| `seniority` | str | Seniority for F-IRB LGD |
| `asset_class` | str | Asset class |

| Output | Type | Description |
|--------|------|-------------|
| `firb` | dict | F-IRB calculation results |
| `airb` | dict | A-IRB calculation results |
| `rwa_difference` | float | A-IRB RWA - F-IRB RWA |
| `rwa_difference_pct` | float | Percentage difference |
| `more_conservative` | str | "F-IRB" or "A-IRB" |

---

## 21. Basel II Counterparty Credit Risk (basel2/counterparty_credit_risk.py)

### `calculate_cem_ead_single()`
**Current Exposure Method EAD for single trade**

| Input | Type | Description |
|-------|------|-------------|
| `trade` | DerivativeTrade | Dataclass with: trade_id, derivative_type, notional, mark_to_market, residual_maturity, counterparty_id, is_protection_seller, is_qualifying_reference |

| Output | Type | Description |
|--------|------|-------------|
| `trade_id` | str | Trade identifier |
| `derivative_type` | str | Type of derivative |
| `notional` | float | Trade notional |
| `mark_to_market` | float | Current MTM |
| `current_exposure` | float | max(0, MTM) |
| `addon_factor` | float | Add-on factor |
| `addon` | float | Notional * addon_factor |
| `ead` | float | CE + Add-on |

**CEM Add-on Factors (% of notional):**

| Derivative Type | <= 1 year | 1-5 years | > 5 years |
|----------------|-----------|-----------|-----------|
| Interest Rate | 0.0% | 0.5% | 1.5% |
| FX/Gold | 1.0% | 5.0% | 7.5% |
| Equity | 6.0% | 8.0% | 10.0% |
| Precious Metals | 7.0% | 7.0% | 8.0% |
| Other Commodities | 10.0% | 12.0% | 15.0% |
| Credit Derivatives | 5.0% | 5.0% | 5.0% |

---

### `calculate_cem_ead_with_netting()`
**CEM EAD with bilateral netting**

| Input | Type | Description |
|-------|------|-------------|
| `trades` | list[DerivativeTrade] | Trades in netting set |
| `netting_set_id` | str | Netting set identifier |

| Output | Type | Description |
|--------|------|-------------|
| `approach` | str | "CEM with Netting" |
| `netting_set_id` | str | Input ID |
| `trade_count` | int | Number of trades |
| `total_mtm` | float | Sum of MTM |
| `net_current_exposure` | float | max(0, total MTM) |
| `gross_current_exposure` | float | Sum of positive MTM |
| `ngr` | float | Net-to-Gross Ratio |
| `gross_addon` | float | Sum of add-ons |
| `net_addon` | float | 0.4*Agross + 0.6*NGR*Agross |
| `gross_ead` | float | EAD without netting |
| `net_ead` | float | Net CE + Net Add-on |
| `netting_benefit` | float | Gross EAD - Net EAD |
| `netting_benefit_pct` | float | Benefit as % |

---

### `calculate_cem_rwa()`
**CEM RWA calculation**

| Input | Type | Description |
|-------|------|-------------|
| `trades` | list[DerivativeTrade] | Trades with counterparty |
| `counterparty_id` | str | Counterparty identifier |
| `counterparty_rw` | float | Counterparty risk weight (%) |
| `has_netting_agreement` | bool | Netting agreement exists |

| Output | Type | Description |
|--------|------|-------------|
| `approach` | str | "CEM" |
| `counterparty_id` | str | Input ID |
| `total_ead` | float | Total EAD |
| `counterparty_rw` | float | Risk weight |
| `rwa` | float | EAD * RW |
| `capital_requirement` | float | RWA * 8% |

---

### `calculate_sm_ead()`
**Standardised Method EAD**

| Input | Type | Description |
|-------|------|-------------|
| `trades` | list[DerivativeTrade] | Trades with counterparty |
| `counterparty_id` | str | Counterparty identifier |

| Output | Type | Description |
|--------|------|-------------|
| `approach` | str | "SM" |
| `counterparty_id` | str | Input ID |
| `beta` | float | 1.4 scaling factor |
| `cmv` | float | Current Market Value (net) |
| `total_risk_position` | float | Aggregated risk positions |
| `hedging_sets` | dict | By asset class |
| `ead` | float | β * max(CMV, TRP) |

---

### `calculate_imm_ead()`
**Internal Model Method EAD**

| Input | Type | Description |
|-------|------|-------------|
| `imm_params` | IMMParameters | Dataclass with: effective_epe, alpha (1.4), maturity |
| `use_bank_alpha` | bool | Use bank-specific alpha |
| `bank_alpha` | float | Bank-specific alpha (if approved) |

| Output | Type | Description |
|--------|------|-------------|
| `approach` | str | "IMM" |
| `effective_epe` | float | Input EPE |
| `alpha` | float | Alpha used |
| `alpha_source` | str | "bank_specific" or "supervisory" |
| `maturity` | float | M parameter |
| `ead` | float | α * Effective EPE |

---

### `calculate_settlement_risk_charge()`
**Settlement risk capital charge (DVP transactions)**

| Input | Type | Description |
|-------|------|-------------|
| `transaction_value` | float | Value of unsettled transaction |
| `days_overdue` | int | Business days past settlement date |
| `is_dvp` | bool | DVP vs free delivery |

| Output | Type | Description |
|--------|------|-------------|
| `transaction_value` | float | Input value |
| `days_overdue` | int | Input days |
| `is_dvp` | bool | Input flag |
| `risk_factor` | float | See table |
| `exposure` | float | Value * risk_factor |
| `capital_charge` | float | Exposure * 8% |

**Settlement Risk Factors:**

| Days Overdue | Risk Factor |
|--------------|-------------|
| 0-4 | 0% |
| 5-15 | 8% |
| 16-30 | 50% |
| 31-45 | 75% |
| 46+ | 100% |

---

## 22. Basel II Operational Risk (basel2/operational_risk.py)

### `calculate_bia_capital()`
**Basic Indicator Approach**

K_BIA = α × Average Gross Income (α = 15%)

| Input | Type | Description |
|-------|------|-------------|
| `gross_income_year1` | float | Gross income T-1 |
| `gross_income_year2` | float | Gross income T-2 |
| `gross_income_year3` | float | Gross income T-3 |
| `alpha` | float | Alpha factor (default: 0.15) |

| Output | Type | Description |
|--------|------|-------------|
| `approach` | str | "BIA" |
| `gross_income` | dict | Yearly values |
| `positive_years_count` | int | Years with positive GI |
| `average_gross_income` | float | Average of positive years |
| `alpha` | float | Alpha factor |
| `capital_requirement` | float | α * avg GI |
| `rwa` | float | Capital * 12.5 |

---

### `calculate_tsa_capital()`
**Standardised Approach with beta factors**

| Input | Type | Description |
|-------|------|-------------|
| `business_line_incomes` | list[BusinessLineIncome] | Dataclass with: business_line, gross_income_year1/2/3 |
| `use_asa` | bool | Use Alternative SA for retail/commercial |
| `retail_loans` | float | Total retail loans (for ASA) |
| `commercial_loans` | float | Total commercial loans (for ASA) |

| Output | Type | Description |
|--------|------|-------------|
| `approach` | str | "TSA" or "ASA" |
| `yearly_capitals` | dict | Capital by year |
| `business_lines` | dict | By business line |
| `capital_requirement` | float | Average of yearly capitals |
| `rwa` | float | Capital * 12.5 |

**TSA Beta Factors:**

| Business Line | Beta |
|--------------|------|
| Corporate Finance | 18% |
| Trading & Sales | 18% |
| Retail Banking | 12% |
| Commercial Banking | 15% |
| Payment & Settlement | 18% |
| Agency Services | 15% |
| Asset Management | 12% |
| Retail Brokerage | 12% |

---

### `calculate_ama_capital()`
**Advanced Measurement Approach**

| Input | Type | Description |
|-------|------|-------------|
| `ama_params` | AMAParameters | Dataclass with: expected_loss, unexpected_loss_999, correlation_adjustment, insurance_mitigation (max 20%), diversification_benefit |
| `business_environment_factor` | float | BEICF adjustment |
| `internal_control_factor` | float | Internal control adjustment |

| Output | Type | Description |
|--------|------|-------------|
| `approach` | str | "AMA" |
| `expected_loss` | float | EL from model |
| `unexpected_loss_999` | float | 99.9% UL |
| `base_capital` | float | UL |
| `correlation_adjustment` | float | Input factor |
| `business_environment_factor` | float | BEICF |
| `insurance_mitigation` | float | Insurance benefit (capped at 20%) |
| `diversification_benefit` | float | Diversification |
| `capital_requirement` | float | Final capital |
| `rwa` | float | Capital * 12.5 |

---

## 23. Basel II Market Risk (basel2/market_risk.py)

### `calculate_smm_capital()`
**Standardised Measurement Method**

| Input | Type | Description |
|-------|------|-------------|
| `positions` | list[MarketRiskPosition] | Dataclass with: asset_class (INTEREST_RATE, EQUITY, FOREIGN_EXCHANGE, COMMODITY), instrument_type, notional, market_value, is_long, rating, residual_maturity, currency, issuer |
| `base_currency` | str | Base currency (default: "USD") |

| Output | Type | Description |
|--------|------|-------------|
| `approach` | str | "SMM" |
| `interest_rate` | dict | specific_risk, general_risk, total |
| `equity` | dict | specific_risk_charge, general_risk_charge, total |
| `fx` | dict | fx_risk_charge |
| `commodity` | dict | directional_risk, basis_risk, total |
| `total_capital` | float | Sum of all charges |
| `rwa` | float | Capital * 12.5 |

**SMM Risk Weights:**

| Asset Class | Specific Risk | General Risk |
|-------------|--------------|--------------|
| IR (Govt AAA-AA) | 0% | Maturity-based |
| IR (Qualifying) | 0.25%-1.6% | Maturity-based |
| IR (Other) | 8% | Maturity-based |
| Equity | 8% | 8% |
| FX | - | 8% |
| Commodities | - | 15% + 3% basis |

---

### `calculate_var_capital()`
**Internal Models Approach (VaR-based)**

| Input | Type | Description |
|-------|------|-------------|
| `var_10day_99` | float | 10-day 99% VaR |
| `stressed_var_10day_99` | float | Stressed VaR (Basel 2.5) |
| `specific_risk_var` | float | Incremental specific risk |
| `multiplication_factor` | float | Base multiplier (min 3) |
| `plus_factor` | float | Backtesting add-on (0-1) |

| Output | Type | Description |
|--------|------|-------------|
| `approach` | str | "IMA (VaR)" |
| `var_10day_99` | float | Input VaR |
| `stressed_var_10day_99` | float | Input sVaR |
| `multiplication_factor` | float | Base multiplier |
| `plus_factor` | float | Backtesting add-on |
| `total_multiplier` | float | mc + plus_factor |
| `general_risk_charge` | float | mc * VaR |
| `stressed_risk_charge` | float | mc * sVaR |
| `specific_risk_charge` | float | Input specific |
| `total_capital` | float | Sum of charges |
| `rwa` | float | Capital * 12.5 |

---

## 24. Basel 2.5 Market Risk Enhancements (basel2/basel25_market_risk.py)

### `calculate_stressed_var_capital()`
**Stressed VaR component (2009 enhancement)**

| Input | Type | Description |
|-------|------|-------------|
| `var_params` | VaRParameters | Dataclass with: var_10day_99, var_1day_99, avg_var_60days, stressed_var_10day_99, avg_stressed_var_60days, stress_period_start, stress_period_end |
| `multiplication_factor` | float | Base multiplier (default: 3.0) |
| `plus_factor` | float | Backtesting add-on |
| `stressed_multiplication_factor` | float | sVaR multiplier |
| `stressed_plus_factor` | float | sVaR add-on |

| Output | Type | Description |
|--------|------|-------------|
| `approach` | str | "Basel 2.5 VaR + sVaR" |
| `var_10day_99` | float | Normal VaR |
| `avg_var_60days` | float | 60-day average VaR |
| `multiplication_factor` | float | mc (3 + plus_factor) |
| `var_component` | float | max(VaR, mc*avgVaR) |
| `stressed_var_10day_99` | float | Stressed VaR |
| `avg_stressed_var_60days` | float | 60-day average sVaR |
| `stressed_multiplication_factor` | float | ms |
| `svar_component` | float | max(sVaR, ms*avgsVaR) |
| `stress_period` | str | Crisis period used |
| `total_capital` | float | VaR + sVaR |
| `rwa` | float | Capital * 12.5 |

---

### `evaluate_backtesting()`
**Backtesting evaluation with traffic light zones**

| Input | Type | Description |
|-------|------|-------------|
| `exceptions_count` | int | Number of VaR exceptions |
| `observation_days` | int | Trading days (default: 250) |

| Output | Type | Description |
|--------|------|-------------|
| `exceptions_count` | int | Input exceptions |
| `observation_days` | int | Input days |
| `expected_exceptions` | float | days * 1% |
| `exception_rate` | float | exceptions / days |
| `zone` | str | "green", "yellow", "red" |
| `plus_factor` | float | See table |
| `total_multiplier` | float | 3 + plus_factor |
| `action_required` | str | Action description |

**Backtesting Plus Factors:**

| Exceptions | Zone | Plus Factor |
|------------|------|-------------|
| 0-4 | Green | 0.00 |
| 5 | Yellow | 0.40 |
| 6 | Yellow | 0.50 |
| 7 | Yellow | 0.65 |
| 8 | Yellow | 0.75 |
| 9 | Yellow | 0.85 |
| 10+ | Red | 1.00 |

---

### `calculate_irc_portfolio()`
**Incremental Risk Charge for credit products**

| Input | Type | Description |
|-------|------|-------------|
| `positions` | list[IRCPosition] | Dataclass with: position_id, issuer, notional, market_value, rating, seniority, liquidity_horizon (months), is_long |
| `correlation` | float | Inter-issuer correlation (default: 0.25) |

| Output | Type | Description |
|--------|------|-------------|
| `approach` | str | "IRC" |
| `confidence_level` | str | "99.9%" |
| `horizon` | str | "1 year" |
| `position_count` | int | Number of positions |
| `correlation_assumption` | float | Input correlation |
| `total_irc_standalone` | float | Sum of individual IRCs |
| `diversification_benefit` | float | Diversification amount |
| `diversified_irc` | float | Final IRC charge |
| `rwa` | float | IRC * 12.5 |
| `positions` | list | Per-position details |

---

### `calculate_crm_charge()`
**Comprehensive Risk Measure for correlation trading**

| Input | Type | Description |
|-------|------|-------------|
| `positions` | list[CorrelationTradingPosition] | Dataclass with: position_id, instrument_type ("cdo_tranche", "nth_to_default", "index_cds"), notional, market_value, attachment, detachment |
| `floor_percentage` | float | Floor as % of specific risk (default: 8%) |

| Output | Type | Description |
|--------|------|-------------|
| `approach` | str | "CRM" |
| `total_notional` | float | Sum of notionals |
| `total_market_value` | float | Sum of MV |
| `total_specific_risk` | float | Base specific risk |
| `floor_percentage` | float | Input floor |
| `crm_floor` | float | Floor amount |
| `crm_charge` | float | max(specific, floor) |
| `rwa` | float | CRM * 12.5 |
| `positions` | list | Per-position details |

**CRM Specific Risk Rates:**

| Tranche Type | Specific Risk |
|--------------|--------------|
| Equity (attachment=0) | 24% |
| Mezzanine (detach<=15%) | 12% |
| Senior | 4% |
| Nth-to-default | 16% |
| Index CDS | 8% |

---

### `calculate_basel25_market_risk_capital()`
**Total Basel 2.5 market risk capital**

| Input | Type | Description |
|-------|------|-------------|
| `var_params` | VaRParameters | VaR/sVaR parameters |
| `irc_positions` | list[IRCPosition] | IRC positions |
| `crm_positions` | list[CorrelationTradingPosition] | CRM positions |
| `backtesting_exceptions` | int | Number of exceptions |
| `specific_risk_charge` | float | Additional specific risk |

| Output | Type | Description |
|--------|------|-------------|
| `approach` | str | "Basel 2.5" |
| `backtesting` | dict | Backtesting evaluation |
| `var_svar` | dict | var_component, svar_component, total |
| `irc` | dict | charge, details |
| `crm` | dict | charge, details |
| `specific_risk` | float | Additional specific risk |
| `total_capital` | float | Sum of all components |
| `total_rwa` | float | Capital * 12.5 |
| `breakdown` | dict | VaR, sVaR, IRC, CRM, Specific |

---

## 25. Basel II Securitization (basel2/securitization.py)

### `calculate_rba_rwa()`
**Ratings-Based Approach**

| Input | Type | Description |
|-------|------|-------------|
| `ead` | float | Tranche exposure |
| `rating` | str | External credit rating |
| `is_senior` | bool | Senior tranche |
| `is_granular` | bool | Granular pool (N>=6) |
| `is_short_term` | bool | Short-term rating |

| Output | Type | Description |
|--------|------|-------------|
| `approach` | str | "Basel II RBA" |
| `ead` | float | Input EAD |
| `rating` | str | Input rating |
| `is_senior` | bool | Input flag |
| `is_granular` | bool | Input flag |
| `risk_weight_pct` | float | Risk weight or 1250% |
| `rwa` | float | Risk-weighted assets |
| `deduction` | float | Amount if below BB- |
| `capital_requirement` | float | 8% of RWA |

**RBA Risk Weights (Senior, Granular):**

| Rating | RW |
|--------|-----|
| AAA | 7% |
| AA | 8% |
| A+ | 10% |
| A | 12% |
| A- | 20% |
| BBB+ | 35% |
| BBB | 60% |
| BBB- | 100% |
| BB+ | 250% |
| BB | 425% |
| BB- | 650% |
| Below BB- | Deduction |

---

### `calculate_sfa_rwa()`
**Supervisory Formula Approach**

| Input | Type | Description |
|-------|------|-------------|
| `ead` | float | Tranche exposure |
| `attachment` | float | Attachment point (e.g., 0.05) |
| `detachment` | float | Detachment point (e.g., 0.15) |
| `kirb` | float | Pool Kirb (or calculated) |
| `underlying_exposures` | list[dict] | Pool for Kirb calc: ead, pd, lgd, maturity |
| `n` | int | Effective number of exposures |
| `lgd_pool` | float | Pool average LGD |

| Output | Type | Description |
|--------|------|-------------|
| `approach` | str | "Basel II SFA" |
| `ead` | float | Tranche EAD |
| `attachment` | float | Attachment point |
| `detachment` | float | Detachment point |
| `thickness` | float | Detachment - Attachment |
| `credit_enhancement` | float | = Attachment |
| `kirb` | float | Pool capital charge |
| `n` | int | Effective N |
| `lgd_pool` | float | Pool LGD |
| `risk_weight_pct` | float | 7%-1250% |
| `rwa` | float | Risk-weighted assets |
| `deduction` | float | If RW >= 1250% |
| `capital_requirement` | float | 8% or full deduction |

---

### `calculate_iaa_rwa()`
**Internal Assessment Approach for ABCP**

| Input | Type | Description |
|-------|------|-------------|
| `ead` | float | Exposure at Default |
| `internal_grade` | int | Bank internal grade (1-12) |
| `is_senior` | bool | Senior tranche |
| `is_granular` | bool | Granular pool |

| Output | Type | Description |
|--------|------|-------------|
| `approach` | str | "Basel II IAA" |
| `ead` | float | Input EAD |
| `internal_grade` | int | Input grade |
| `mapped_rating` | str | Equivalent external rating |
| `is_senior` | bool | Input flag |
| `is_granular` | bool | Input flag |
| `risk_weight_pct` | float | Based on RBA table |
| `rwa` | float | Risk-weighted assets |
| `deduction` | float | If applicable |
| `capital_requirement` | float | 8% of RWA |

**IAA Grade Mapping:**

| Internal Grade | External Rating |
|---------------|-----------------|
| 1 | AAA |
| 2 | AA |
| 3-5 | A+/A/A- |
| 6-8 | BBB+/BBB/BBB- |
| 9-11 | BB+/BB/BB- |
| 12 | Below BB- |

---

## 26. Basel II Credit Risk Mitigation (basel2/credit_risk_mitigation.py)

### `calculate_simple_approach_rwa()`
**Simple CRM approach (collateral substitution)**

| Input | Type | Description |
|-------|------|-------------|
| `ead` | float | Exposure at Default |
| `exposure_rw` | float | Exposure risk weight (%) |
| `collateral_type` | CollateralType | CASH, GOLD, DEBT_SECURITIES_*, EQUITY_* |
| `collateral_value` | float | Collateral value |
| `collateral_rating` | str | Rating for debt collateral |

| Output | Type | Description |
|--------|------|-------------|
| `approach` | str | "Simple" |
| `ead` | float | Input EAD |
| `exposure_rw` | float | Input RW |
| `collateral_type` | str | Input type |
| `collateral_value` | float | Input value |
| `collateral_rw` | float | Collateral RW (20% floor) |
| `collateralized_portion` | float | min(collateral, EAD) |
| `uncollateralized_portion` | float | EAD - collateralized |
| `rwa_collateralized` | float | collateralized * coll_rw |
| `rwa_uncollateralized` | float | uncollateralized * exp_rw |
| `total_rwa` | float | Sum of RWAs |
| `rwa_without_crm` | float | EAD * exposure_rw |
| `rwa_reduction` | float | Benefit from CRM |

---

### `calculate_exposure_with_collateral()`
**Comprehensive approach (haircut-based)**

E* = max(0, [E × (1 + He) - C × (1 - Hc - Hfx)])

| Input | Type | Description |
|-------|------|-------------|
| `ead` | float | Exposure at Default |
| `exposure_rw` | float | Exposure risk weight (%) |
| `collateral_value` | float | Market value of collateral |
| `collateral_type` | CollateralType | Type of collateral |
| `collateral_rating` | str | Collateral rating |
| `residual_maturity` | float | Collateral maturity (years) |
| `is_sovereign` | bool | Sovereign issuer |
| `currency_mismatch` | bool | FX mismatch (+8% haircut) |
| `exposure_haircut` | float | He for repos |

| Output | Type | Description |
|--------|------|-------------|
| `approach` | str | "Comprehensive" |
| `original_ead` | float | Input EAD |
| `exposure_rw` | float | Input RW |
| `exposure_haircut` | float | He applied |
| `adjusted_exposure` | float | E * (1 + He) |
| `collateral` | dict | Haircut calculation details |
| `adjusted_collateral` | float | C * (1 - Hc - Hfx) |
| `exposure_after_crm` | float | E* |
| `rwa` | float | E* * RW |
| `rwa_without_crm` | float | EAD * RW |
| `rwa_reduction` | float | Benefit |
| `rwa_reduction_pct` | float | Percentage benefit |

**Supervisory Haircuts (10-day holding period):**

| Collateral | <= 1 year | 1-5 years | > 5 years |
|-----------|-----------|-----------|-----------|
| Cash | 0% | 0% | 0% |
| Gold | 15% | 15% | 15% |
| Sovereign AAA-AA | 0.5% | 2% | 4% |
| Sovereign A-BBB | 1% | 3% | 6% |
| Bank/Corp AAA-AA | 1% | 4% | 8% |
| Bank/Corp A-BBB | 2% | 6% | 12% |
| Main Index Equity | 15% | - | - |
| Other Equity | 25% | - | - |
| Currency Mismatch | +8% | +8% | +8% |

---

### `calculate_exposure_with_guarantee()`
**Guarantee substitution approach**

| Input | Type | Description |
|-------|------|-------------|
| `ead` | float | Exposure at Default |
| `exposure_rw` | float | Obligor risk weight (%) |
| `guarantee_value` | float | Guarantee amount |
| `guarantor_rw` | float | Guarantor risk weight (%) |
| `is_proportional` | bool | Proportional coverage |

| Output | Type | Description |
|--------|------|-------------|
| `approach` | str | "Guarantee Substitution" |
| `ead` | float | Input EAD |
| `exposure_rw` | float | Obligor RW |
| `guarantee_value` | float | Input guarantee |
| `guarantor_rw` | float | Guarantor RW |
| `protected_portion` | float | min(guarantee, EAD) |
| `unprotected_portion` | float | EAD - protected |
| `rwa_protected` | float | protected * guarantor_rw |
| `rwa_unprotected` | float | unprotected * exposure_rw |
| `total_rwa` | float | Sum of RWAs |
| `rwa_without_crm` | float | EAD * exposure_rw |
| `rwa_reduction` | float | Benefit from guarantee |

---

### `calculate_netting_benefit()`
**On-balance sheet netting**

| Input | Type | Description |
|-------|------|-------------|
| `loans` | float | Total loans to counterparty |
| `deposits` | float | Total deposits from counterparty |
| `is_legally_enforceable` | bool | Netting legally enforceable |

| Output | Type | Description |
|--------|------|-------------|
| `approach` | str | "On-Balance Sheet Netting" |
| `gross_loans` | float | Input loans |
| `deposits` | float | Input deposits |
| `is_legally_enforceable` | bool | Input flag |
| `net_exposure` | float | max(0, loans - deposits) |
| `netting_benefit` | float | loans - net_exposure |
| `netting_ratio` | float | benefit / loans |

---

## 27. Basel II Equity Banking Book (basel2/equity_banking_book.py)

### `calculate_simple_rw_rwa()`
**Simple Risk Weight Method**

| Input | Type | Description |
|-------|------|-------------|
| `position` | EquityPosition | Dataclass with: position_id, issuer, equity_type (PUBLICLY_TRADED, PRIVATELY_HELD, etc.), fair_value, cost_basis, ownership_percentage |
| `use_national_discretion` | bool | Apply national discretion |
| `discretion_type` | str | "diversified_portfolio" (200%) or "government_development" (100%) |

| Output | Type | Description |
|--------|------|-------------|
| `approach` | str | "Simple Risk Weight" |
| `position_id` | str | Input ID |
| `issuer` | str | Issuer name |
| `equity_type` | str | Type of equity |
| `fair_value` | float | Current value |
| `cost_basis` | float | Original cost |
| `unrealized_gain` | float | FV - cost |
| `base_risk_weight` | float | Base RW |
| `applied_risk_weight` | float | After discretion |
| `rw_source` | str | "standard" or "national_discretion_*" |
| `rwa` | float | FV * RW |
| `capital_requirement` | float | RWA * 8% |

**Simple Risk Weight Risk Weights:**

| Equity Type | Risk Weight |
|-------------|-------------|
| Publicly Traded | 300% |
| Privately Held | 400% |
| Private Equity | 400% |
| Speculative | 400% |
| Hedge Fund | 400% |
| Significant Investment | 400% |

---

### `calculate_imm_rwa()`
**Internal Models Method for equity**

| Input | Type | Description |
|-------|------|-------------|
| `position` | EquityPosition | Equity position details |
| `var_params` | EquityVaRParameters | Dataclass with: var_99_quarterly, var_99_annual, model_type, observation_period_years |
| `use_annual_var` | bool | Use annual horizon |

| Output | Type | Description |
|--------|------|-------------|
| `approach` | str | "Internal Models" |
| `position_id` | str | Input ID |
| `issuer` | str | Issuer name |
| `fair_value` | float | Current value |
| `var_horizon` | str | "quarterly" or "annual" |
| `var_99` | float | 99% VaR |
| `model_type` | str | VaR model type |
| `rwa_from_var` | float | VaR * 12.5 |
| `floor_risk_weight` | float | 200% floor |
| `rwa_floor` | float | FV * 200% |
| `floor_binding` | bool | Whether floor applies |
| `rwa` | float | max(VaR RWA, floor) |
| `implied_risk_weight` | float | Effective RW |
| `capital_requirement` | float | RWA * 8% |

---

### `calculate_pd_lgd_rwa()`
**PD/LGD approach for equity (A-IRB banks)**

| Input | Type | Description |
|-------|------|-------------|
| `position` | EquityPosition | Equity position details |
| `pd` | float | Probability of Default |
| `lgd` | float | LGD (90% floor) |
| `maturity` | float | Effective maturity (default: 5 years) |

| Output | Type | Description |
|--------|------|-------------|
| `approach` | str | "PD/LGD" |
| `position_id` | str | Input ID |
| `issuer` | str | Issuer name |
| `equity_type` | str | Type of equity |
| `fair_value` | float | Current value |
| `pd` | float | PD used (floored at 5bps) |
| `lgd` | float | LGD used (floored at 90%) |
| `maturity` | float | Maturity used |
| `correlation` | float | Asset correlation |
| `capital_k` | float | Capital requirement K |
| `calculated_rw` | float | K * 12.5 * 100 |
| `floor_rw` | float | 200% (public) or 300% (other) |
| `applied_rw` | float | max(calculated, floor) |
| `floor_binding` | bool | Whether floor applies |
| `rwa` | float | FV * applied_rw |
| `expected_loss` | float | PD * LGD * FV |
| `capital_requirement` | float | RWA * 8% |

---

### `compare_equity_approaches()`
**Compare all three equity approaches**

| Input | Type | Description |
|-------|------|-------------|
| `position` | EquityPosition | Equity position |
| `var_params` | EquityVaRParameters | For IMM |
| `pd` | float | For PD/LGD |

| Output | Type | Description |
|--------|------|-------------|
| `position` | str | Position ID |
| `fair_value` | float | Position value |
| `simple_rw` | dict | Simple RW results |
| `imm` | dict | IMM results |
| `pd_lgd` | dict | PD/LGD results |
| `most_conservative` | str | Highest RWA approach |
| `least_conservative` | str | Lowest RWA approach |
| `ranking` | list | Approaches by RWA |

---

### `calculate_significant_investment_treatment()`
**Significant investment deduction (>10% ownership)**

| Input | Type | Description |
|-------|------|-------------|
| `investment_value` | float | Fair value of investment |
| `bank_cet1_capital` | float | Bank's CET1 capital |
| `ownership_percentage` | float | Ownership stake (e.g., 0.15) |
| `investee_is_bank` | bool | Investee is bank/FI |

| Output | Type | Description |
|--------|------|-------------|
| `investment_value` | float | Input value |
| `ownership_percentage` | float | Input stake |
| `is_significant` | bool | > 10% ownership |
| `investee_is_bank` | bool | Input flag |
| `treatment` | str | "capital_deduction", "risk_weighted_400", "normal" |
| `deduction_amount` | float | Amount deducted from capital |
| `rwa` | float | If risk-weighted |
| `threshold_amount` | float | 10% of CET1 |
| `exceeds_threshold` | bool | Value > threshold |
