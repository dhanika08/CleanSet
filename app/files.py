"""files.py - small helper shared by the web app and the scripts: pick the readable files in a folder."""
import os

READABLE = (".pdf", ".png", ".jpg", ".jpeg", ".txt", ".html")


def collect_files(folder):
    """Every readable file in a folder. If a PDF exists for a page, its HTML twin is skipped."""
    names = sorted(os.listdir(folder))
    stems_with_pdf = {os.path.splitext(n)[0] for n in names if n.lower().endswith(".pdf")}
    files = []
    for n in names:
        ext = os.path.splitext(n)[1].lower()
        if ext not in READABLE:
            continue
        if ext == ".html" and os.path.splitext(n)[0] in stems_with_pdf:
            continue
        with open(os.path.join(folder, n), "rb") as f:
            files.append((n, f.read()))
    return files
