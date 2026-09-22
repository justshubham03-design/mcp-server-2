from enum import Enum
from typing import List, Dict, Any
from pydantic import BaseModel, Field

class ThemeCategory(str, Enum):
    KYC_ONBOARDING = "kyc_onboarding"
    PAYMENTS_SETTLEMENT = "payments_settlement"
    TRADING_EXECUTION = "trading_execution"
    MUTUAL_FUNDS_STATEMENTS = "mutual_funds_statements"
    APP_PERFORMANCE_UI = "app_performance_ui"

class TaxonomyDefinition(BaseModel):
    id: ThemeCategory
    name: str
    description: str
    keywords: List[str] = Field(default_factory=list)

GROWW_TAXONOMY: Dict[ThemeCategory, TaxonomyDefinition] = {
    ThemeCategory.KYC_ONBOARDING: TaxonomyDefinition(
        id=ThemeCategory.KYC_ONBOARDING,
        name="KYC, Onboarding & Account Opening",
        description="User verification, Aadhaar OTP, PAN verification, signature match, document rejection, and account activation.",
        keywords=[
            "kyc", "onboarding", "aadhaar", "pan", "verification", "account opening", 
            "rejected", "reject", "document", "signature", "digilocker", "activate",
            "activation", "photo", "re-kyc", "nominee"
        ]
    ),
    ThemeCategory.PAYMENTS_SETTLEMENT: TaxonomyDefinition(
        id=ThemeCategory.PAYMENTS_SETTLEMENT,
        name="Payments, UPI, Fund Transfers & Withdrawals",
        description="UPI deposits, bank mandates, autopay, withdrawal delays, settlement cycles, and wallet balance updates.",
        keywords=[
            "upi", "deposit", "withdraw", "withdrawal", "funds", "fund", "money deducted", 
            "bank transfer", "autopay", "mandate", "refund", "credited", "debit", "wallet", 
            "settlement", "t+1", "payment failed", "google pay", "phonepe", "paytm"
        ]
    ),
    ThemeCategory.TRADING_EXECUTION: TaxonomyDefinition(
        id=ThemeCategory.TRADING_EXECUTION,
        name="Order Execution, F&O, Stock Trading & Charts",
        description="Stock buying/selling, Options chain, Futures & Options (F&O), Candlestick charts, Stop-loss, GTT orders, order latency.",
        keywords=[
            "chart", "charts", "f&o", "option", "options", "call", "put", "stop loss", "stoploss", 
            "gtt", "order rejected", "latency", "market order", "limit order", "candlestick", 
            "tradingview", "nifty", "banknifty", "sensex", "intraday", "delivery", "strike"
        ]
    ),
    ThemeCategory.MUTUAL_FUNDS_STATEMENTS: TaxonomyDefinition(
        id=ThemeCategory.MUTUAL_FUNDS_STATEMENTS,
        name="Mutual Funds, SIPs & Account Statements / P&L",
        description="Mutual fund investing, SIP installments, step-up SIP, portfolio tracking, P&L statements, and Capital Gains tax reports.",
        keywords=[
            "sip", "mutual fund", "mutual funds", "nav", "portfolio", "p&l", "statement", 
            "tax report", "capital gains", "ltcg", "stcg", "dividend", "step up", "step-up", 
            "cams", "kfintech", "folio", "units"
        ]
    ),
    ThemeCategory.APP_PERFORMANCE_UI: TaxonomyDefinition(
        id=ThemeCategory.APP_PERFORMANCE_UI,
        name="App Performance, Glitches, Login & UI/UX",
        description="App crashes, freezes, login errors, OTP delays, biometric authentication, dark mode, navigation, and overall user interface.",
        keywords=[
            "crash", "crashes", "lag", "login", "otp", "slow", "freeze", "freezes", 
            "ui", "ux", "update", "black screen", "fingerprint", "biometric", "bug", 
            "bugs", "glitch", "glitches", "server down", "stuck", "interface", "dark mode"
        ]
    )
}
