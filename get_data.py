"""Download the Survey of Consumer Finances summary extracts and replicate
weights, 1989-2025, and compute median net worth for families with children by
the education of the reference person, with 95% confidence intervals.

Source: Federal Reserve Board, SCF summary extract public data (CSV) and
replicate weight files (Stata), one zip each per survey wave:
https://www.federalreserve.gov/econres/scfindex.htm

The Fed re-releases every wave's extract in the dollars of the latest survey,
so these files are all in 2025 dollars. When the 2028 survey comes out, the
same URLs will return 2028-dollar files.

"Families with children" follows the Fed's KIDS variable: the family has at
least one child of the reference person or spouse/partner living in the
household, of any age (adult children living at home count).

Standard errors follow the Fed's MEANIT macro in the SCF codebook: sampling
variance from the 999 replicate weights (times multiplicity factors) on the
first implicate, plus 6/5 times the variance of the estimate across the five
implicates. The 95% interval is the estimate +/- 1.96 standard errors.

Outputs:
  data/raw/                              untouched downloads
  data/scf_families.csv                  one row per family x implicate, slim columns
  data/median_networth_kids_by_educ.csv  the series plot.py draws
"""

import io
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import requests

YEARS = [1989, 1992, 1995, 1998, 2001, 2004, 2007, 2010, 2013, 2016, 2019, 2022, 2025]
FILES = "https://www.federalreserve.gov/econres/files/"
COLUMNS = ["WGT", "EDCL", "KIDS", "NETWORTH"]
N_REPLICATES = 999
Z95 = 1.96

# EDCL: education of the reference person.
# 1 = no high school diploma, 2 = high school diploma or GED,
# 3 = some college or associate degree, 4 = bachelor's degree or more.
GROUPS = {"hs_or_less": [1, 2], "bachelors_plus": [4]}

# Fed Table 4 (2025 historical tables, public data, 2025 dollars):
# median net worth of all families, thousands. Used to check that the downloads
# and the median calculation reproduce the Fed's published numbers.
FED_ALL_FAMILIES_MEDIAN = {
    1989: 118.74, 1992: 112.70, 1995: 122.43, 1998: 143.07, 2001: 158.91,
    2004: 160.09, 2007: 189.49, 2010: 115.09, 2013: 113.39, 2016: 131.32,
    2019: 154.47, 2022: 210.89, 2025: 216.10,
}

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "data" / "raw"


def extract_name(year):
    return f"scfp{year}excel.zip"


def replicate_name(year):
    # Waves before 2001 use two-digit years in the file name.
    return f"scf{year % 100:02d}rw1s.zip" if year < 2001 else f"scf{year}rw1s.zip"


def download(name):
    path = RAW / name
    if not path.exists():
        print(f"downloading {name}")
        resp = requests.get(FILES + name, timeout=600)
        resp.raise_for_status()
        path.write_bytes(resp.content)
    return path


def read_member(path, suffix):
    with zipfile.ZipFile(path) as zf:
        (member,) = [n for n in zf.namelist() if n.lower().endswith(suffix)]
        return io.BytesIO(zf.read(member))


def read_extract(year):
    df = pd.read_csv(read_member(download(extract_name(year)), ".csv"))
    # Case and implicate IDs are YY1/Y1 or XX1/X1 depending on the wave;
    # Y1 = 10 * YY1 + implicate.
    case = "YY1" if "YY1" in df.columns else "XX1"
    row = "Y1" if case == "YY1" else "X1"
    out = df[COLUMNS].copy()
    out.insert(0, "case", df[case])
    out.insert(1, "implicate", df[row] - 10 * df[case])
    return out


def read_replicates(year):
    rw = pd.read_stata(read_member(download(replicate_name(year)), ".dta"))
    rw.columns = rw.columns.str.lower()
    case = "yy1" if "yy1" in rw.columns else "xx1"
    weights = rw[[f"wt1b{i}" for i in range(1, N_REPLICATES + 1)]].fillna(0).clip(lower=0)
    mult = rw[[f"mm{i}" for i in range(1, N_REPLICATES + 1)]].fillna(0).clip(lower=0)
    return pd.DataFrame(weights.values * mult.values, index=rw[case].astype(int))


def weighted_median(values, weights):
    # Pools all five implicates, as the Fed does for its published medians.
    order = np.argsort(values, kind="stable")
    cum = np.cumsum(weights[order])
    return values[order][np.searchsorted(cum, cum[-1] / 2)]


def median_draws(group, replicates):
    """Pooled median, the five per-implicate medians, and the 999 replicate
    medians (first implicate only) for one group of families."""
    pooled = weighted_median(group.NETWORTH.values, group.WGT.values)
    by_implicate = np.array([
        weighted_median(g.NETWORTH.values, g.WGT.values)
        for _, g in group.groupby("implicate")
    ])
    first = group[group.implicate == 1]
    order = np.argsort(first.NETWORTH.values, kind="stable")
    values = first.NETWORTH.values[order]
    cum = np.cumsum(replicates.loc[first.case.values].values[order], axis=0)
    by_replicate = values[(cum >= cum[-1] / 2).argmax(axis=0)]
    return pooled, by_implicate, by_replicate


def standard_error(by_implicate, by_replicate):
    return np.sqrt(6 / 5 * np.var(by_implicate, ddof=1) + np.var(by_replicate, ddof=1))


def main():
    RAW.mkdir(parents=True, exist_ok=True)

    frames = []
    rows = []
    for year in YEARS:
        df = read_extract(year)
        replicates = read_replicates(year)

        all_median = weighted_median(df.NETWORTH.values, df.WGT.values) / 1e3
        expected = FED_ALL_FAMILIES_MEDIAN[year]
        assert abs(all_median - expected) < 0.01, (year, all_median, expected)

        kids = df[df.KIDS > 0]
        row = {"year": year}
        draws = {}
        for name, codes in GROUPS.items():
            g = kids[kids.EDCL.isin(codes)]
            pooled, by_implicate, by_replicate = median_draws(g, replicates)
            se = standard_error(by_implicate, by_replicate)
            draws[name] = (by_implicate, by_replicate)
            row[f"median_{name}"] = pooled
            row[f"lo_{name}"] = pooled - Z95 * se
            row[f"hi_{name}"] = pooled + Z95 * se
            row[f"share_{name}"] = g.WGT.sum() / kids.WGT.sum()
            # Unweighted families in the group (each family appears 5 times).
            row[f"n_{name}"] = len(g) // 5

        row["ratio"] = row["median_bachelors_plus"] / row["median_hs_or_less"]
        (hi_imp, hi_rep), (lo_imp, lo_rep) = draws["bachelors_plus"], draws["hs_or_less"]
        se = standard_error(hi_imp / lo_imp, hi_rep / lo_rep)
        row["lo_ratio"] = row["ratio"] - Z95 * se
        row["hi_ratio"] = row["ratio"] + Z95 * se
        rows.append(row)

        df.insert(0, "year", year)
        frames.append(df)

    pd.concat(frames, ignore_index=True).to_csv(ROOT / "data" / "scf_families.csv", index=False)
    out = pd.DataFrame(rows)
    out.to_csv(ROOT / "data" / "median_networth_kids_by_educ.csv", index=False)
    print("all-families medians match Fed Table 4 for every wave")
    show = out[["year", "median_hs_or_less", "lo_hs_or_less", "hi_hs_or_less",
                "median_bachelors_plus", "lo_bachelors_plus", "hi_bachelors_plus",
                "ratio", "lo_ratio", "hi_ratio"]].copy()
    show.iloc[:, 1:7] /= 1e3
    print(show.round(1).to_string(index=False))


if __name__ == "__main__":
    main()
