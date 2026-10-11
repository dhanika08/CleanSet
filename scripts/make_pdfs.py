"""
make_pdfs.py - creates any PDFs that are still missing, and skips the ones that already exist.

Use it when make_gold.py printed "PDF failed" warnings, or got stopped half way. It is safe to
run as many times as you like. Each run only does the work that is left.

Run from the project root:   python3 scripts/make_pdfs.py
"""
import glob
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from render import find_chrome, html_to_pdf


def main():
    chrome = find_chrome()
    if not chrome:
        print("Google Chrome was not found, so PDFs cannot be made. Tell me and we will continue with the HTML files.")
        return 1
    pages = sorted(glob.glob("data/demo/planted/*.html") + glob.glob("data/demo/clean/*.html") + glob.glob("data/gold/*/docs/*.html"))
    todo = [p for p in pages if not (os.path.exists(p[:-5] + ".pdf") and os.path.getsize(p[:-5] + ".pdf") > 0)]
    print("%d pages in total, %d PDFs already exist, %d still to make." % (len(pages), len(pages) - len(todo), len(todo)))
    failed = []
    for i, p in enumerate(todo, 1):
        ok = html_to_pdf(chrome, p)
        print("  [%d/%d] %s %s" % (i, len(todo), "ok    " if ok else "FAILED", p))
        if not ok:
            failed.append(p)
    done = len(glob.glob("data/**/*.pdf", recursive=True))
    print("\nFinished. PDFs now on disk: %d (expected %d)." % (done, len(pages)))
    if failed:
        print("%d failed. Run this script again. If the same ones keep failing, send me the list." % len(failed))
        return 1
    print("All PDFs are in place.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
