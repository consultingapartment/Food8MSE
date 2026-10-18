"""Тогтмол утгууд."""

BASE_URL = "https://open.mse.mn"

#: Судалж буй компаниуд (тикер -> нэр).
COMPANIES = {
    "APU": "АПУ ХК",
    "TUM": "Түмэн шувуут ХК",
    "TCK": "Талх чихэр ХК",
    "SUU": "Сүү ХК",
    "MFC": "Монос хүнс ХК",
    "GAZR": "Газар шим үйлдвэр ХК",
    "MMX": "Мах импекс ХК",
    "MGLA": "Эм Жи Эл Акуа ХК",
}

#: /securities хуудсыг задлах боломжгүй үед ашиглах companyCode (2026-10 байдлаар шалгасан).
KNOWN_IDS = {
    "APU": 90,
    "TUM": 549,
    "TCK": 22,
    "SUU": 135,
    "MFC": 551,
    "GAZR": 565,
    "MMX": 208,
    "MGLA": 572,
}

USER_AGENT = "Mozilla/5.0 (compatible; mse-financials/1.0; +https://github.com)"
DEFAULT_REPORTS_DIR = "mse_reports"
DEFAULT_OUTPUT = "reports/FOOD mse.xlsx"
TIMEZONE = "Asia/Ulaanbaatar"

#: Гэрчилгээний гинж дутуу (SSLError) үед ЗӨВХӨН эдгээр домэйнд баталгаажуулалтгүй дахин оролдоно.
#: `--strict-ssl` өгвөл огт оролдохгүй.
INSECURE_FALLBACK_DOMAINS = ("mse.mn",)
