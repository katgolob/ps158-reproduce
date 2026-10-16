"""First figure: median net worth of families with children, by education of
the reference person, 1989-2025 (Survey of Consumer Finances, 2025 dollars),
with 95% confidence bands.

Run get_data.py first.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#e4e3df"
SERIES = {
    "bachelors_plus": ("Bachelor's degree or more", "#2a78d6"),
    "hs_or_less": ("High school or less", "#eb6834"),
}


def style(ax):
    ax.set_facecolor(SURFACE)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ["top", "right", "left"]:
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(INK_2)
    ax.tick_params(colors=INK_2, length=0, labelsize=9)


def main():
    df = pd.read_csv(ROOT / "data" / "median_networth_kids_by_educ.csv")
    years = df.year

    fig, (top, bottom) = plt.subplots(
        2, 1, figsize=(8, 7), sharex=True, height_ratios=[2, 1], facecolor=SURFACE
    )

    for key, (label, color) in SERIES.items():
        y = df[f"median_{key}"] / 1e3
        top.fill_between(years, df[f"lo_{key}"] / 1e3, df[f"hi_{key}"] / 1e3,
                         color=color, alpha=0.15, linewidth=0)
        top.plot(years, y, color=color, linewidth=2, marker="o", markersize=5, label=label)
        top.annotate(f"${y.iloc[-1]:,.0f}k", (years.iloc[-1], y.iloc[-1]),
                     xytext=(8, 0), textcoords="offset points", va="center",
                     fontsize=9, color=INK)
    top.set_ylabel("Median net worth\n(thousands of 2025 dollars)", color=INK_2, fontsize=9)
    top.set_ylim(bottom=0)
    top.legend(frameon=False, fontsize=9, loc="upper left", labelcolor=INK)
    style(top)

    bottom.fill_between(years, df.lo_ratio, df.hi_ratio, color=INK_2, alpha=0.15, linewidth=0)
    bottom.plot(years, df.ratio, color=INK_2, linewidth=2, marker="o", markersize=5)
    for i in [0, df.ratio.idxmax(), len(df) - 1]:
        bottom.annotate(f"{df.ratio[i]:.1f}×", (years[i], df.ratio[i]),
                        xytext=(0, 8), textcoords="offset points", ha="center",
                        fontsize=9, color=INK)
    bottom.set_ylabel("Ratio\n(bachelor's+ ÷ HS or less)", color=INK_2, fontsize=9)
    bottom.set_ylim(0, df.hi_ratio.max() * 1.1)
    bottom.set_xticks(years)
    bottom.set_xlim(years.min() - 1.5, years.max() + 3)
    style(bottom)

    fig.suptitle("The wealth gap by parents' education, families with children, 1989–2025",
                 x=0.06, y=0.985, ha="left", fontsize=12, color=INK)
    fig.text(0.06, 0.95,
             "Families with at least one child of the reference person or spouse/partner living at home,\n"
             "of any age (adult children included). Shaded bands are 95% confidence intervals.",
             va="top", fontsize=9, color=INK_2)
    fig.text(0.06, 0.015,
             "Education is that of the SCF reference person. Weighted medians pool all five implicates. "
             "Confidence intervals combine\n999 replicate weights and imputation variance (Fed MEANIT method). "
             "Source: Federal Reserve Board, Survey of Consumer Finances.",
             fontsize=7.5, color=INK_2)
    fig.tight_layout(rect=(0.02, 0.05, 1, 0.9))

    out = ROOT / "figures" / "networth_gap_kids.png"
    out.parent.mkdir(exist_ok=True)
    fig.savefig(out, dpi=200, facecolor=SURFACE)
    print(f"wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
