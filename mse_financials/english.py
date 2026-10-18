"""Англи шошготой тайлан (жишээ нь АПУ-гийн 2026 Q2: `BS`/`IS`, "Items") -> загварын түлхүүр.

Маягт нь Сангийн сайдын стандарт маягттай ижил боловч мөрийн нэр англи, дугаарлалт нь өөр
(`1.1.20` = Total current assets) тул нэрээр (хэвийн болгосон хэлбэрээр) түлхүүр рүү шууд холбоно.
Эх файлын (алдаатай) бичгийн хэлбэрийг ("adminstration", "Foriegn", "evalaution") ч оруулсан.
"""
from __future__ import annotations

import re

from .template import BS, IS, norm

_BS = {
    "Cash and cash equivalents": "cash",
    "Trade receivables": "receivable",
    "Tax and social insurance receivables": "tax_receivable",
    "Other receivables": "other_receivable",
    "Other financial assets": "other_fin_assets",
    "Inventories": "inventory",
    "Prepayments": "prepaid",
    "Other current assets": "other_ca",
    "Assets held for sale": "held_for_sale",
    "Total current assets": "total_ca",
    "Property, plant and equipment": "ppe",
    "Intangible assets": "intangible",
    "Biological assets": "biological",
    "Long-term investments": "lt_investment",
    "Mining and evalaution assets": "exploration",
    "Mining and evaluation assets": "exploration",
    "Deferred tax assets": "deferred_tax_asset",
    "Assets held for investment": "investment_property",
    "Other non-current assets": "other_nca",
    "Goodwill": "goodwill",
    "Total non-current assets": "total_nca",
    "Total assets": "total_assets",
    "Trade payables": "payable",
    "Salary payables": "wages_payable",
    "Tax payables": "tax_payable",
    "Social insurance payables": "social_payable",
    "Short-term loans and borrowings": "st_loan",
    "Interest payables": "interest_payable",
    "Dividend payables": "dividend_payable",
    "Prepaid income": "deferred_income",
    "Contingent liabilities short term": "st_provision",
    "Other short term payables": "other_stl",
    "Payables involved in assets held for a sale": "held_for_sale_liab",
    "Total current liabilities": "total_stl",
    "Long-term loans and borrowings": "lt_loan",
    "Contingent liabilities long term": "lt_provision",
    "Deferred tax liabilities": "deferred_tax_liab",
    "Long-term other payable": "other_ltl",
    "Total non-current liabilities": "total_ltl",
    "Total liabilities": "total_liabilities",
    "Common stock": "share_capital",
    "Treasury stock": "treasury",
    "Paid in capital": "paid_in",
    "Revaluation reserve": "revaluation",
    "Foreign currency translation reserve": "fx_reserve",
    "Other reserves": "other_equity",
    "Retained earnings": "retained",
    "Non-controlling interest": "equity_nci",
    "Total equity": "total_equity",
    "Total liabilities and equity": "total_le",
}

_IS = {
    "Revenue": "revenue",
    "Cost of sales": "cogs",
    "Gross profit": "gross_profit",
    "Rent income": "rent_income",
    "Interest income": "interest_income",
    "Dividend income": "dividend_income",
    "Royalty income": "fee_income",
    "Other income": "other_income",
    "Sales and marketing expenses": "selling_exp",
    "General and adminstration expenses": "admin_exp",
    "General and administration expenses": "admin_exp",
    "Finance expense": "finance_cost",
    "Other expense": "other_exp",
    "Foriegn exchange gain or (loss)": "fx_gain",
    "Foreign exchange gain or (loss)": "fx_gain",
    "Proceed from disposed tangible assets": "ppe_disposal",
    "Proceed from disposed intangible assets": "intangible_disposal",
    "Gain or (loss) from sales of investments": "investment_gain",
    "Profit before tax": "profit_before_tax",
    "Corporation income tax": "income_tax",
    "Profit after tax": "profit_after_tax",
    "Profit or loss from ceasing operation": "discontinued",
    "Net profit": "net_income",
    "Other comprehensive income": "oci",
    "Revaluation recognition": "oci_revaluation",
    "Foriegn currency translation": "oci_fx",
    "Foreign currency translation": "oci_fx",
    "Remeasurement of employee benefit provision": "oci_remeasure",
    "Total other comprehensive income:": "total_comprehensive",
    "Total comprehensive income": "total_comprehensive",
}
_OTHER_GAIN = "othergainorloss"        # IS-д хоёр удаа гарна: эхнийх нь бусад ашиг, "Other comprehensive income"-ийн дараах нь OCI

EN_KEYS = {BS: {norm(k): v for k, v in _BS.items()}, IS: {norm(k): v for k, v in _IS.items()}}
CYRILLIC_RE = re.compile(r"[а-яөүёА-ЯӨҮЁ]")


def is_english(label: str) -> bool:
    return bool(label) and not CYRILLIC_RE.search(label) and bool(re.search(r"[A-Za-z]{3}", label))


def english_key(statement: str, label: str, after_oci: bool) -> str | None:
    """Англи шошгыг загварын түлхүүр болгоно. `after_oci`: "Other comprehensive income" мөрийн ДАРАА байгаа эсэх."""
    n = norm(label)
    if n == _OTHER_GAIN:
        return "oci_other_gain" if after_oci else "other_profit"
    return EN_KEYS.get(statement, {}).get(n)
