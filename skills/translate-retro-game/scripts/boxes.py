"""Box gate: every text group has a measured box with a shot, and every English line fits the box it lands in.

    python -X utf8 boxes.py TEXT.tsv BOXES.tsv [--root .]

TEXT.tsv   one "id<TAB>group<TAB>jp<TAB>en" per string, written by the project (newlines as the two characters \\n).
           group = the box the string is drawn in: a table column, a window type, a menu field. One string shown in
           two boxes goes in once per box (id#2), so it gets the smaller budget.
BOXES.tsv  one "group<TAB>wrap<TAB>line_max<TAB>shot<TAB>note" per group (# comments ok):
             self    the box breaks lines by itself every N cells, mid-word in English (the JP relies on it): store the
                     English pre-wrapped; line_max = the longest line that draws inside the box (often under N)
             stored  the box draws the stored breaks only; line_max = the longest line that draws inside the box
             none    one-line field; line_max = its width in cells
             px      the project's pixel lint owns this width (VWF); only the row and the shot are checked here
           shot = a screenshot (path from --root) of this box showing a real string, measured: the proof it was seen.
Cells: full-width characters count 2, others 1 (a 12 px kanji = two 6 px letters on most fixed-width engines).

Fails (exit 1) on: a group with no row or no shot file; English lines over line_max; a group not marked self whose
JP lines run past line_max, which means the box wraps by itself (66 of 82 mails broke mid-word and ran off the box
after the same bug was fixed for one other column only).
"""
import argparse
import os
import sys
import unicodedata
from collections import defaultdict

WRAPS = {"self", "stored", "none", "px"}


def cells(s):
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def longest(text):
    return max((cells(line) for line in text.replace("\\n", "\n").split("\n")), default=0)


def read_tsv(path, ncol):
    rows = []
    with open(path, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            line = line.rstrip("\r\n")
            if not line.strip() or line.startswith("#"):
                continue
            cols = line.split("\t")
            if len(cols) < ncol:
                sys.exit(f"{path}:{n}: {len(cols)} columns, want {ncol}")
            rows.append(cols)
    return rows


def problems(text_rows, box_rows, root="."):
    boxes = {r[0]: r for r in box_rows}
    groups = defaultdict(list)
    for id_, group, jp, en, *_ in text_rows:
        groups[group].append((id_, jp, en))
    out = []
    for group, rows in sorted(groups.items()):
        jp_max = max(longest(jp) for _, jp, _ in rows)
        if group not in boxes:
            out.append(f"{group}: no box row (JP lines run to {jp_max} cells); measure it in game, add it to BOXES.tsv")
            continue
        _, wrap, line_max, shot, *_ = boxes[group]
        if wrap not in WRAPS:
            out.append(f"{group}: wrap {wrap!r}, want one of {sorted(WRAPS)}")
            continue
        if not shot or not os.path.isfile(os.path.join(root, shot)):
            out.append(f"{group}: no shot file {shot!r}: tour a screen that shows this box, then measure it")
        if wrap == "px":
            continue
        try:
            lim = int(line_max)
        except ValueError:
            out.append(f"{group}: line_max {line_max!r} is not a number")
            continue
        if wrap != "self" and jp_max > lim:
            out.append(f"{group}: JP lines run to {jp_max} cells, past line_max {lim}: the box wraps by itself "
                       "(mid-word in English); measure where it breaks and mark it self")
        over = [(id_, longest(en)) for id_, _, en in rows if en and longest(en) > lim]
        if over:
            what = "breaks mid-word in game" if wrap == "self" else "runs past the box"
            ids = ", ".join(f"{i} ({n})" for i, n in over[:5]) + (f" +{len(over) - 5} more" if len(over) > 5 else "")
            out.append(f"{group}: {len(over)} English lines over {lim} cells ({what}): {ids}")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("text")
    ap.add_argument("boxes")
    ap.add_argument("--root", default=".", help="base for shot paths (default: current directory)")
    a = ap.parse_args(argv)
    bad = problems(read_tsv(a.text, 4), read_tsv(a.boxes, 4), a.root)
    for p in bad:
        print(p)
    print(f"boxes: {len(bad)} problems")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
