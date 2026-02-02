"""
Basel II RWA Calculator

Implementation of Basel II regulatory capital methodologies (2004 framework)
including Basel 2.5 enhancements (2009).

Modules:
--------
Core Credit Risk:
- credit_risk_sa: Standardised Approach for Credit Risk
- credit_risk_irb: IRB Foundation and Advanced approaches
- credit_risk_mitigation: CRM techniques (simple and comprehensive)

Counterparty Credit Risk:
- counterparty_credit_risk: CEM, SM, IMM, Settlement Risk, Wrong-Way Risk

Securitization:
- securitization: RBA, SFA, and IAA approaches

Market Risk:
- market_risk: Standardised Measurement Method and VaR
- basel25_market_risk: Stressed VaR, IRC, CRM (Basel 2.5 enhancements)

Operational Risk:
- operational_risk: BIA, TSA, and AMA approaches

Equity:
- equity_banking_book: Simple RW, Internal Models, PD/LGD approaches

Key Differences from Basel III/IV:
----------------------------------
1. Operational Risk: BIA/TSA/AMA vs SMA
2. Market Risk: VaR-based vs FRTB (ES-based)
3. CCR: CEM/SM vs SA-CCR
4. No output floor (72.5%)
5. No leverage ratio requirement (3%)
6. Different securitization hierarchy
7. Basel 2.5 added stressed VaR and IRC after 2008 crisis
"""

# Credit Risk - Standardised Approach
from .credit_risk_sa import (
    calculate_sa_rwa,
    calculate_batch_sa_rwa,
    get_sovereign_rw,
    get_bank_rw,
    get_corporate_rw,
    get_retail_rw,
    get_real_estate_rw,
    calculate_off_balance_sheet_ead,
    # PD-based wrappers
    calculate_sa_rwa_from_pd,
    calculate_batch_sa_rwa_from_pd,
)

# Credit Risk - IRB Approaches
from .credit_risk_irb import (
    calculate_irb_rwa,
    calculate_firb_rwa,
    calculate_airb_rwa,
    calculate_correlation,
    calculate_capital_requirement,
    calculate_batch_irb_rwa,
    compare_firb_vs_airb,
    calculate_slotting_rwa,
    RATING_TO_PD,
    get_rating_from_pd,
)

# Counterparty Credit Risk
from .counterparty_credit_risk import (
    calculate_cem_ead_single,
    calculate_cem_ead_with_netting,
    calculate_cem_ead_counterparty,
    calculate_cem_rwa,
    calculate_sm_ead,
    calculate_imm_ead,
    calculate_settlement_risk_charge,
    assess_wrong_way_risk,
    compare_ccr_approaches,
    DerivativeTrade,
    DerivativeType,
    IMMParameters,
)

# Operational Risk
from .operational_risk import (
    calculate_bia_capital,
    calculate_tsa_capital,
    calculate_ama_capital,
    compare_oprisk_approaches,
    BusinessLine,
    BusinessLineIncome,
    AMAParameters,
)

# Market Risk - Basel II
from .market_risk import (
    calculate_smm_capital,
    calculate_var_capital,
    calculate_specific_risk,
    calculate_general_risk,
    calculate_ir_specific_risk,
    calculate_ir_general_risk,
    calculate_equity_risk,
    calculate_fx_risk,
    calculate_commodity_risk,
    AssetClass,
    MarketRiskPosition,
)

# Market Risk - Basel 2.5 Enhancements
from .basel25_market_risk import (
    calculate_stressed_var_capital,
    calculate_irc_portfolio,
    calculate_irc_position,
    calculate_crm_charge,
    calculate_basel25_market_risk_capital,
    evaluate_backtesting,
    calculate_securitization_specific_risk,
    VaRParameters,
    IRCPosition,
    CorrelationTradingPosition,
    # PD-based wrappers
    create_irc_position_from_pd,
    calculate_irc_position_from_pd,
    calculate_irc_portfolio_from_pd,
    calculate_securitization_specific_risk_from_pd,
)

# Securitization
from .securitization import (
    calculate_rba_rwa,
    calculate_sfa_rwa,
    calculate_iaa_rwa,
    compare_securitization_approaches,
    get_rba_risk_weight,
    # PD-based wrappers
    calculate_rba_rwa_from_pd,
    calculate_iaa_rwa_from_pd,
    compare_securitization_approaches_from_pd,
)

# Credit Risk Mitigation
from .credit_risk_mitigation import (
    calculate_exposure_with_collateral,
    calculate_exposure_with_guarantee,
    calculate_comprehensive_haircut,
    calculate_simple_approach_rwa,
    calculate_netting_benefit,
    get_supervisory_haircut,
    CollateralType,
)

# Equity Banking Book
from .equity_banking_book import (
    calculate_simple_rw_rwa,
    calculate_imm_rwa,
    calculate_pd_lgd_rwa,
    calculate_equity_portfolio_rwa,
    compare_equity_approaches,
    calculate_significant_investment_treatment,
    EquityPosition,
    EquityType,
    EquityApproach,
    EquityVaRParameters,
)


__all__ = [
    # SA Credit Risk
    "calculate_sa_rwa",
    "calculate_batch_sa_rwa",
    "get_sovereign_rw",
    "get_bank_rw",
    "get_corporate_rw",
    "get_retail_rw",
    "get_real_estate_rw",
    "calculate_off_balance_sheet_ead",
    "calculate_sa_rwa_from_pd",
    "calculate_batch_sa_rwa_from_pd",
    # IRB Credit Risk
    "calculate_irb_rwa",
    "calculate_firb_rwa",
    "calculate_airb_rwa",
    "calculate_correlation",
    "calculate_capital_requirement",
    "calculate_batch_irb_rwa",
    "compare_firb_vs_airb",
    "calculate_slotting_rwa",
    "RATING_TO_PD",
    "get_rating_from_pd",
    # Counterparty Credit Risk
    "calculate_cem_ead_single",
    "calculate_cem_ead_with_netting",
    "calculate_cem_ead_counterparty",
    "calculate_cem_rwa",
    "calculate_sm_ead",
    "calculate_imm_ead",
    "calculate_settlement_risk_charge",
    "assess_wrong_way_risk",
    "compare_ccr_approaches",
    "DerivativeTrade",
    "DerivativeType",
    "IMMParameters",
    # Operational Risk
    "calculate_bia_capital",
    "calculate_tsa_capital",
    "calculate_ama_capital",
    "compare_oprisk_approaches",
    "BusinessLine",
    "BusinessLineIncome",
    "AMAParameters",
    # Market Risk
    "calculate_smm_capital",
    "calculate_var_capital",
    "calculate_specific_risk",
    "calculate_general_risk",
    "calculate_ir_specific_risk",
    "calculate_ir_general_risk",
    "calculate_equity_risk",
    "calculate_fx_risk",
    "calculate_commodity_risk",
    "AssetClass",
    "MarketRiskPosition",
    # Basel 2.5 Market Risk
    "calculate_stressed_var_capital",
    "calculate_irc_portfolio",
    "calculate_irc_position",
    "calculate_crm_charge",
    "calculate_basel25_market_risk_capital",
    "evaluate_backtesting",
    "calculate_securitization_specific_risk",
    "VaRParameters",
    "IRCPosition",
    "CorrelationTradingPosition",
    "create_irc_position_from_pd",
    "calculate_irc_position_from_pd",
    "calculate_irc_portfolio_from_pd",
    "calculate_securitization_specific_risk_from_pd",
    # Securitization
    "calculate_rba_rwa",
    "calculate_sfa_rwa",
    "calculate_iaa_rwa",
    "compare_securitization_approaches",
    "get_rba_risk_weight",
    "calculate_rba_rwa_from_pd",
    "calculate_iaa_rwa_from_pd",
    "compare_securitization_approaches_from_pd",
    # CRM
    "calculate_exposure_with_collateral",
    "calculate_exposure_with_guarantee",
    "calculate_comprehensive_haircut",
    "calculate_simple_approach_rwa",
    "calculate_netting_benefit",
    "get_supervisory_haircut",
    "CollateralType",
    # Equity Banking Book
    "calculate_simple_rw_rwa",
    "calculate_imm_rwa",
    "calculate_pd_lgd_rwa",
    "calculate_equity_portfolio_rwa",
    "compare_equity_approaches",
    "calculate_significant_investment_treatment",
    "EquityPosition",
    "EquityType",
    "EquityApproach",
    "EquityVaRParameters",
]
