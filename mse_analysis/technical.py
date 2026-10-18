"""Техник шинжилгээ: MA, RSI, MACD, Bollinger, Gann HiLo, BJ HEMA, тулгуур/эсэргүүцэл, BOS/CHoCH, Wyckoff, дохионы оноо.

Хугацаа: өдөр (D), долоо хоног (W), сар (M). Бүгд цэвэр Python (pandas шаардахгүй).
Томьёо нь `5_bank_dashboard_buildspec.json` ба Pine Script (Gann HiLo + BJ HEMA)-тэй нийцнэ.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from .prices import Bar

TIMEFRAMES = (("D", "Өдөр"), ("W", "Долоо хоног"), ("M", "Сар"))
MA_PERIODS = (7, 29, 99)


# ------------------------------------------------------------------ хугацаа
def resample(bars: list[Bar], tf: str) -> list[Bar]:
    if tf == "D":
        return list(bars)
    groups: dict[tuple, list[Bar]] = {}
    for b in bars:
        key = (b.day.isocalendar()[0], b.day.isocalendar()[1]) if tf == "W" else (b.day.year, b.day.month)
        groups.setdefault(key, []).append(b)
    out = []
    for key in sorted(groups):
        g = sorted(groups[key], key=lambda b: b.day)
        out.append(Bar(g[-1].day, g[0].open, max(b.high for b in g), min(b.low for b in g), g[-1].close,
                       sum(b.qty for b in g), sum(b.value for b in g)))
    return out


# ------------------------------------------------------------------ үндсэн индикатор
def sma(xs: list[float], n: int) -> list[Optional[float]]:
    out: list[Optional[float]] = [None] * len(xs)
    s = 0.0
    for i, x in enumerate(xs):
        s += x
        if i >= n:
            s -= xs[i - n]
        if i >= n - 1:
            out[i] = s / n
    return out


def ema(xs: list[float], n: int) -> list[float]:
    """pandas ewm(adjust=False): y0 = x0, y = α·x + (1−α)·y."""
    a = 2 / (n + 1)
    out: list[float] = []
    for i, x in enumerate(xs):
        out.append(x if i == 0 else a * x + (1 - a) * out[-1])
    return out


def rsi(closes: list[float], n: int = 14) -> list[Optional[float]]:
    """Buildspec: gain/loss-ийн n-ийн гүйлтийн дундаж."""
    out: list[Optional[float]] = [None] * len(closes)
    gains = [0.0] + [max(closes[i] - closes[i - 1], 0.0) for i in range(1, len(closes))]
    losses = [0.0] + [max(closes[i - 1] - closes[i], 0.0) for i in range(1, len(closes))]
    for i in range(n, len(closes)):
        g = sum(gains[i - n + 1:i + 1]) / n
        l = sum(losses[i - n + 1:i + 1]) / n
        out[i] = 100.0 if l == 0 and g > 0 else 50.0 if l == 0 else 100 - 100 / (1 + g / l)
    return out


def macd(closes: list[float], fast: int = 12, slow: int = 26, signal: int = 9):
    ef, es = ema(closes, fast), ema(closes, slow)
    line = [a - b for a, b in zip(ef, es)]
    sig = ema(line, signal)
    return line, sig, [a - b for a, b in zip(line, sig)]


def bollinger(closes: list[float], n: int = 20, k: float = 2.0):
    """Pine ta.stdev = популяцийн хазайлт."""
    mid = sma(closes, n)
    up: list[Optional[float]] = [None] * len(closes)
    lo: list[Optional[float]] = [None] * len(closes)
    for i in range(n - 1, len(closes)):
        w = closes[i - n + 1:i + 1]
        mu = mid[i]
        sd = math.sqrt(sum((x - mu) ** 2 for x in w) / n)
        up[i], lo[i] = mu + k * sd, mu - k * sd
    return mid, up, lo


def gann_hilo(bars: list[Bar], length: int = 3, displace: int = 1):
    """hilo: 1 = өсөх, −1 = буурах. Шугам: буурахад SMA(high), өсөхөд SMA(low)."""
    hi, lo = sma([b.high for b in bars], length), sma([b.low for b in bars], length)
    state: list[int] = []
    line: list[Optional[float]] = []
    cur = 0
    for i, b in enumerate(bars):
        j = i - displace
        if j >= 0 and hi[j] is not None and lo[j] is not None:
            if b.close > hi[j]:
                cur = 1
            elif b.close < lo[j]:
                cur = -1
            line.append(hi[j] if cur == -1 else lo[j])
        else:
            line.append(None)
        state.append(cur)
    return state, line


def bj_hema(bars: list[Bar], periods=(5, 9, 21)):
    """Heiken Ashi нээлтийн EMA 5/9/21 (Bjorgum Triple EMA)."""
    ha_close = [(b.open + b.high + b.low + b.close) / 4 for b in bars]
    ha_open: list[float] = []
    for i, b in enumerate(bars):
        ha_open.append((b.open + b.close) / 2 if i == 0 else (ha_open[-1] + ha_close[i - 1]) / 2)
    emas = [ema(ha_open, p) for p in periods]
    colors = []
    for i, b in enumerate(bars):
        up = b.close > emas[0][i] and b.close > emas[1][i]
        dn = b.close < emas[0][i] and b.close < emas[1][i]
        colors.append("өсөх" if up else "буурах" if dn else "саармаг")
    return emas, colors


# ------------------------------------------------------------------ бүтэц (тулгуур, SMC, Wyckoff)
def fractal_levels(bars: list[Bar], window: int = 5, lookback: int = 300, tol: float = 1.025, n: int = 3):
    """(тулгуурууд, эсэргүүцлүүд): фрактал экстремумыг ±2.5%-иар бүлэглэж, олон давтагдсаныг сонгоно."""
    seg = bars[-lookback:]
    last = seg[-1].close
    hs, ls = [], []
    for i in range(window, len(seg) - window):
        w = seg[i - window:i + window + 1]
        if seg[i].high == max(b.high for b in w):
            hs.append(seg[i].high)
        if seg[i].low == min(b.low for b in w):
            ls.append(seg[i].low)

    def cluster(levels: list[float]) -> list[tuple[float, int]]:
        groups: list[list[float]] = []
        for lv in sorted(levels):
            if groups and lv <= groups[-1][0] * tol:
                groups[-1].append(lv)
            else:
                groups.append([lv])
        return [(sum(g) / len(g), len(g)) for g in groups]

    sup = sorted(cluster([x for x in ls if x < last]), key=lambda t: -t[1])[:n]
    res = sorted(cluster([x for x in hs if x > last]), key=lambda t: -t[1])[:n]
    supports = sorted(v for v, _ in sup)
    resist = sorted(v for v, _ in res)
    while len(supports) < 1:                              # бодит түвшин олдохгүй бол зохиомол
        supports.append(last * 0.90)
    while len(resist) < 1:
        resist.append(last * 1.10)
    return supports, resist


def swings(bars: list[Bar], window: int = 3) -> list[tuple[int, str, float]]:
    """Фрактал swing; дараалсан ижил төрлийг илүү туйлшрсанаар нь нэгтгэж H,L,H,L болгоно."""
    raw = []
    for i in range(window, len(bars) - window):
        w = bars[i - window:i + window + 1]
        hs = [b.high for b in w]
        ls = [b.low for b in w]
        if bars[i].high == max(hs) and hs.count(bars[i].high) == 1:
            raw.append((i, "H", bars[i].high))
        elif bars[i].low == min(ls) and ls.count(bars[i].low) == 1:
            raw.append((i, "L", bars[i].low))
    out: list[tuple[int, str, float]] = []
    for s in raw:
        if out and out[-1][1] == s[1]:
            if (s[1] == "H" and s[2] > out[-1][2]) or (s[1] == "L" and s[2] < out[-1][2]):
                out[-1] = s
        else:
            out.append(s)
    return out


def smc(bars: list[Bar], sw: list[tuple[int, str, float]]):
    """BOS/CHoCH үйл явдал + тэнцүү өндөр/нам (liquidity)."""
    last_h = last_l = None
    trend = None
    events = []
    for i, kind, val in sw:
        if kind == "H":
            if last_h is not None and val > last_h:
                events.append((bars[i].day, "HH", "CHoCH" if trend == "down" else "BOS", val))
                trend = "up"
            last_h = val
        else:
            if last_l is not None and val < last_l:
                events.append((bars[i].day, "LL", "CHoCH" if trend == "up" else "BOS", val))
                trend = "down"
            last_l = val
    highs = [v for _, k, v in sw if k == "H"][-14:]
    lows = [v for _, k, v in sw if k == "L"][-14:]

    def equal(vs):
        return sorted({round((a + b) / 2, 4) for i, a in enumerate(vs) for b in vs[i + 1:] if abs(a - b) / max(a, b) < 0.005})

    return trend, events[-4:], equal(highs), equal(lows)


def wyckoff(bars: list[Bar], lookback: int = 60) -> str:
    seg = bars[-lookback:]
    if len(seg) < 20:
        return "Өгөгдөл дутуу"
    hi, lo = max(b.high for b in seg), min(b.low for b in seg)
    if hi == lo:
        return "Шилжилтийн үе"
    pos = (seg[-1].close - lo) / (hi - lo)
    h = len(seg) // 2
    a, b = seg[:h], seg[h:]
    rng = lambda s: max(x.high for x in s) - min(x.low for x in s)           # noqa: E731
    contracting = rng(b) < 0.72 * rng(a)
    if pos < 0.35 and contracting:
        return "Хуримтлал (Accumulation)"
    if pos > 0.65 and contracting:
        return "Түгээлт (Distribution)"
    if pos > 0.6 and not contracting:
        return "Өсөлтийн үе (Markup)"
    if pos < 0.4 and not contracting:
        return "Уналтын үе (Markdown)"
    return "Шилжилтийн үе"


# ------------------------------------------------------------------ дохионы оноо
def scenario(close, ma_f, ma_m, ma_s, macd_v, macd_sig, rsi_v, resistance) -> dict:
    """Статистик баталгаагүй, дохионы тооноос гаргасан ойролцоо жин."""
    score = 0
    if ma_f is not None and close > ma_f:
        score += 1
    if None not in (ma_f, ma_m) and ma_f > ma_m:
        score += 1
    if None not in (ma_m, ma_s) and ma_m > ma_s:
        score += 1
    if macd_v > macd_sig:
        score += 1
    else:
        score -= 1
    if rsi_v is not None:
        if 45 <= rsi_v <= 70:
            score += 1
        if rsi_v < 30:
            score -= 1
        if rsi_v > 75:
            score -= 1
    if None not in (ma_f, ma_m) and ma_f < ma_m:
        score -= 1
    up = min(max(40 + score * 8, 15), 70)
    down = min(max(30 - score * 7, 10), 60)
    side = max(100 - up - down, 0)
    tot = up + down + side
    stars_trend = 5 if score >= 3 else 4 if score >= 1 else 3 if score >= -1 else 2 if score >= -3 else 1
    if macd_v > macd_sig and rsi_v is not None and rsi_v > 55:
        mom = 5
    elif macd_v > macd_sig:
        mom = 4
    elif rsi_v is not None and rsi_v < 35:
        mom = 2
    else:
        mom = 3
    risk = 1 if rsi_v is not None and (rsi_v > 75 or rsi_v < 20) else 3
    dist = (resistance - close) / close if resistance else None
    brk = 3 if dist is None else 5 if dist < 0.03 else 4 if dist < 0.06 else 3
    return {"score": score, "up": up / tot * 100, "down": down / tot * 100, "side": side / tot * 100,
            "stars": {"Чиг хандлага": stars_trend, "Импульс": mom, "Аюулгүй байдал": risk, "Тулгуур давах": brk}}


# ------------------------------------------------------------------ нэгтгэл
@dataclass
class TechResult:
    ticker: str
    tf: str
    bars: list[Bar]
    series: dict[str, list]
    state: dict


def analyze(ticker: str, bars: list[Bar], tf: str) -> Optional[TechResult]:
    b = resample(bars, tf)
    if len(b) < 30:
        return None
    closes = [x.close for x in b]
    mas = {p: sma(closes, p) for p in MA_PERIODS}
    rs = rsi(closes)
    m_line, m_sig, m_hist = macd(closes)
    bb_mid, bb_up, bb_lo = bollinger(closes)
    g_state, g_line = gann_hilo(b)
    emas, colors = bj_hema(b)
    sup, res = fractal_levels(b)
    sw = swings(b)
    trend, events, eq_h, eq_l = smc(b, sw)
    i = len(b) - 1
    scn = scenario(closes[i], mas[7][i], mas[29][i], mas[99][i], m_line[i], m_sig[i], rs[i],
                   min(res) if res else None)
    g_since = i
    while g_since > 0 and g_state[g_since - 1] == g_state[i]:
        g_since -= 1
    pb = None if bb_up[i] is None or bb_up[i] == bb_lo[i] else (closes[i] - bb_lo[i]) / (bb_up[i] - bb_lo[i])
    state = {
        "last_day": b[i].day, "close": closes[i], "bars": len(b),
        "ma7": mas[7][i], "ma29": mas[29][i], "ma99": mas[99][i], "rsi": rs[i],
        "macd": m_line[i], "macd_signal": m_sig[i], "macd_hist": m_hist[i],
        "bb_up": bb_up[i], "bb_lo": bb_lo[i], "bb_pctb": pb,
        "gann": "ӨСӨХ" if g_state[i] == 1 else "БУУРАХ" if g_state[i] == -1 else "—", "gann_line": g_line[i],
        "gann_since": b[g_since].day, "gann_flip_recent": g_since >= i - 2 and g_since > 0,
        "bj_color": colors[i], "bj_ema5": emas[0][i], "bj_ema9": emas[1][i], "bj_ema21": emas[2][i],
        "support": sup, "resistance": res, "smc_trend": {"up": "ӨСӨХ", "down": "БУУРАХ"}.get(trend, "—"),
        "smc_events": events, "equal_highs": eq_h[-3:], "equal_lows": eq_l[:3], "wyckoff": wyckoff(b),
        "scenario": scn,
    }
    series = {"ma7": mas[7], "ma29": mas[29], "ma99": mas[99], "rsi": rs, "macd": m_line, "signal": m_sig,
              "hist": m_hist, "bb_mid": bb_mid, "bb_up": bb_up, "bb_lo": bb_lo, "gann": g_line, "gann_state": g_state,
              "bj5": emas[0], "bj9": emas[1], "bj21": emas[2], "bj_color": colors}
    return TechResult(ticker, tf, b, series, state)
