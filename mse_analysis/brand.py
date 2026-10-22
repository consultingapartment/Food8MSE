"""Зураг бүрийн яг голд бичигдэх тэмдэг: «Powered by Big Short Ganbayar & openmindMSE» — «MSE» нь ногоон өнгөтэй.

Тэмдэг тунгалаг (өгөгдлийг халхалдаггүй), хоёр өнгийн хэсгийг нэг мөрөнд голлуулж байрлуулна.
"""
from __future__ import annotations

TEXT_LEFT = "Powered by Big Short Ganbayar & openmind"
TEXT_GREEN = "MSE"
GREEN = "#12a150"          # «MSE» (ногоон)
GREY = "#3d4752"           # урд хэсэг
ALPHA_GREY, ALPHA_GREEN = 0.30, 0.55
SIZE = 30


def stamp(fig) -> None:
    """`fig`-ийн голд (0.5, 0.5) тэмдгийг нэмнэ. savefig-ийн өмнө дуудна."""
    fig.canvas.draw()                                              # текстийн хэмжээг тооцоход renderer хэрэгтэй
    rend = fig.canvas.get_renderer()
    a = fig.text(0, 0.5, TEXT_LEFT, fontsize=SIZE, fontweight="bold", color=GREY, alpha=ALPHA_GREY,
                 ha="left", va="center", zorder=100)
    b = fig.text(0, 0.5, TEXT_GREEN, fontsize=SIZE, fontweight="bold", color=GREEN, alpha=ALPHA_GREEN,
                 ha="left", va="center", zorder=100)
    inv = fig.transFigure.inverted()
    wa = inv.transform((a.get_window_extent(rend).width, 0))[0]
    wb = inv.transform((b.get_window_extent(rend).width, 0))[0]
    x0 = 0.5 - (wa + wb) / 2
    a.set_x(x0)
    b.set_x(x0 + wa)
    a.set_gid("brand")
    b.set_gid("brand")
