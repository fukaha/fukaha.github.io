#!/usr/bin/env python3
"""The site logo: a pointed arch with a crescent finial, a twelve-pointed girih star inside it and an
open book at its foot. Writes _includes/mark.html (the header and footer mark, coloured by CSS),
assets/img/logo.svg (full colour, for print and press) and assets/img/favicon.svg.

Usage: python3 tools/logo.py
"""
from math import cos, sin, pi
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GOLD, RED, NAVY, TEAL = "#c9a24a", "#741d2d", "#1f3a4d", "#0091ad"
CX, CY = 50, 57  # centre of the star


def f(x):
    return f"{x:.2f}".rstrip("0").rstrip(".")


def pt(r, a):
    return f"{f(CX + r * sin(a))} {f(CY - r * cos(a))}"


def star(n, R, r, turn=0.0):
    """A closed n-pointed star path, outer radius R, inner radius r, one point straight up."""
    step = pi / n
    return "M" + "L".join(pt(R if i % 2 == 0 else r, turn + i * step) for i in range(2 * n)) + "Z"


def polygon(n, r, turn=0.0):
    return "M" + "L".join(pt(r, turn + i * 2 * pi / n) for i in range(n)) + "Z"


def arch(half, top, foot, shoulder):
    """A four-centred arch: sides at CX±half from the foot up to the shoulder, meeting in a point."""
    l, r = CX - half, CX + half
    k = (shoulder - top)
    return (f"M{f(l)} {f(foot)}V{f(shoulder)}C{f(l)} {f(shoulder - 0.45 * k)} {f(CX - 0.28 * half)} {f(top + 0.3 * k)} {f(CX)} {f(top)}"
            f"C{f(CX + 0.28 * half)} {f(top + 0.3 * k)} {f(r)} {f(shoulder - 0.45 * k)} {f(r)} {f(shoulder)}V{f(foot)}")


R_OUT, R_IN = 27, 19.5   # the gold star
R_CORE, R_CORE_IN = 11.5, 8  # the red heart
OUTER = arch(40, 15, 93, 47)
INNER = arch(33.5, 23.5, 93, 50)
STAR = star(12, R_OUT, R_IN)
# the lines cut through the gold: an inset outline, twelve spokes and a ring, which make the petals
CUTS = (star(12, R_OUT - 4.2, R_IN - 3.1) +
        "".join(f"M{pt(R_IN - 3.1, (2 * i + 1) * pi / 12)}L{pt(R_CORE + 2.2, (2 * i + 1) * pi / 12)}" for i in range(12)) +
        polygon(12, R_CORE + 2.2, pi / 12))
CORE = star(12, R_CORE, R_CORE_IN)
CORE_EYE = star(6, 4.2, 2.4)
FINIAL = "M50 15V10"
BALL = (50, 9.6, 1.7)
CRESCENT = "M47.01 2.39A3.4 3.4 0 0 0 52.99 2.39A3.0 3.0 0 0 1 47.01 2.39Z"
BOOK = ("M50 97.2C40 92.6 25 91.4 6 93.6V100C25 97.8 40 99 50 104.4C60 99 75 97.8 94 100V93.6C75 91.4 60 92.6 50 97.2Z")
PAGES = ("M50 93.4C41 89.2 27 88.2 11 89.6M50 93.4C59 89.2 73 88.2 89 89.6"
         "M50 97.2V93.4")
VIEW = "0 0 100 106"


def body(u, line, gold, red, eye, arch2):
    return (
        f'<defs><mask id="{u}c" maskUnits="userSpaceOnUse" x="0" y="0" width="100" height="106">'
        f'<rect width="100" height="106" fill="#fff"/><path d="{CUTS}" fill="none" stroke="#000" stroke-width="1.3" stroke-linejoin="round"/></mask></defs>'
        f'<path d="{OUTER}" fill="none" stroke="{gold}" stroke-width="3.2" stroke-linejoin="round"/>'
        f'<path d="{INNER}" fill="none" stroke="{arch2}" stroke-width="2" stroke-linejoin="round"/>'
        f'<path d="{FINIAL}" stroke="{gold}" stroke-width="1.8"/><circle cx="{BALL[0]}" cy="{BALL[1]}" r="{BALL[2]}" fill="{gold}"/>'
        f'<path d="{CRESCENT}" fill="{gold}"/>'
        f'<path d="{STAR}" fill="{gold}" mask="url(#{u}c)"/>'
        f'<path d="{CORE}" fill="{red}"/><path d="{CORE_EYE}" fill="{eye}"/>'
        f'<path d="{PAGES}" fill="none" stroke="{gold}" stroke-width="1.8" stroke-linecap="round"/>'
        f'<path d="{BOOK}" fill="{line}"/>'
    )


def main():
    mark = ('{%- comment -%}\nThe site mark (tools/logo.py writes it): a pointed arch with a crescent finial, a twelve-pointed\n'
            'girih star and an open book. Its colours come from CSS: --mk-line (arch and book), --mk-gold, --mk-red.\n'
            'id: prefix for the mask id, unique on the page\n{%- endcomment -%}\n'
            '{%- assign _u = include.id | default: "mk" -%}\n'
            f'<svg class="mark" viewBox="{VIEW}" aria-hidden="true" focusable="false">'
            + body("{{ _u }}", "var(--mk-line, currentColor)", "var(--mk-gold, #c9a24a)", "var(--mk-red, #741d2d)",
                   "var(--mk-gold, #c9a24a)", "var(--mk-line, currentColor)") + "</svg>\n")
    (ROOT / "_includes/mark.html").write_text(mark, encoding="utf-8")

    logo = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{VIEW}" width="500" height="530">'
            f'<title>Fukahâ</title>' + body("lg", NAVY, GOLD, RED, GOLD, TEAL) + "</svg>\n")
    (ROOT / "assets/img/logo.svg").write_text(logo, encoding="utf-8")

    # favicon: the arch and star alone on a navy tile, legible at 16 px
    fav = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48"><rect width="48" height="48" rx="10" fill="#1f3a4d"/>'
           '<g transform="translate(24 25.5) scale(0.46) translate(-50 -57)">'
           f'<defs><mask id="fc" maskUnits="userSpaceOnUse" x="0" y="0" width="100" height="106"><rect width="100" height="106" fill="#fff"/>'
           f'<path d="{star(12, R_OUT - 4.8, R_IN - 3.6)}" fill="none" stroke="#000" stroke-width="2.4"/></mask></defs>'
           f'<path d="{arch(40, 13, 104, 47)}" fill="none" stroke="{GOLD}" stroke-width="6" stroke-linejoin="round"/>'
           f'<path d="{STAR}" fill="{GOLD}" mask="url(#fc)"/><path d="{CORE}" fill="#b8404f"/></g></svg>\n')
    (ROOT / "assets/img/favicon.svg").write_text(fav, encoding="utf-8")
    print("mark.html, logo.svg, favicon.svg yazıldı")


if __name__ == "__main__":
    main()
