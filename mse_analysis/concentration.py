"""Хувьцаа эзэмшлийн төвлөрөл ба хөрвөх чадварын эрсдэл."""
from __future__ import annotations

from .inputs import Ownership


def assess(o: Ownership) -> dict:
    avg_big = o.big_pct / o.big_holders if o.big_holders else 0.0
    if o.small_pct < 0.10 or avg_big >= 0.50 or o.small_holders < 1000:
        grade = "ӨНДӨР"
    elif o.small_pct >= 0.25 and o.small_holders >= 5000:
        grade = "БАГА"
    else:
        grade = "ДУНД"
    why = []
    if o.small_pct < 0.10:
        why.append(f"чөлөөт эргэлт ердөө {o.small_pct:.1%}")
    if avg_big >= 0.50:
        why.append(f"том эзэмшигч дунджаар {avg_big:.1%}-ийг дангаар эзэмшдэг")
    if o.small_holders < 1000:
        why.append(f"жижиг эзэмшигч цөөн ({o.small_holders:,})")
    return {"grade": grade, "avg_big": avg_big, "reasons": "; ".join(why)}
