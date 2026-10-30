"""Check an image submission issue, and apply it when approved.

Usage: python scripts/check_image.py check|apply   (issue body in $ISSUE_BODY)
Writes a Markdown comment to comment.md and prints ok=true/false for GitHub Actions.
"""
import json, os, re, sys, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FREE = re.compile(r"^(cc0|cc-?zero|public domain|pd\b|pd-|no restrictions|cc[ -]by(-sa)?[ -]\d)", re.I)
NOT_FREE = re.compile(r"\b(nc|nd)\b|non-?commercial|no-?deriv", re.I)
UA = {"User-Agent": "MesozoicCarousel/1.0 (https://github.com/sayantandatta/mesozoic-carousel)"}


def field(body, label):
    m = re.search(r"^###\s*" + re.escape(label) + r"\s*\n+(.*?)(?=\n###\s|\Z)", body, re.S | re.M)
    v = (m.group(1).strip() if m else "")
    return "" if v == "_No response_" else v


def file_name(raw):
    raw = urllib.parse.unquote(raw.strip().strip("<>`")).split("?")[0].split("#")[0]
    raw = re.sub(r"^https?://[^/]+/(wiki/)?", "", raw)
    raw = re.sub(r"^(File|Image):", "", raw, flags=re.I).replace("_", " ").strip()
    return raw


def commons(f):
    q = urllib.parse.urlencode({"action": "query", "format": "json", "formatversion": 2, "titles": "File:" + f,
                                "prop": "imageinfo", "iiprop": "url|mime|size|extmetadata", "iiurlwidth": 640})
    with urllib.request.urlopen(urllib.request.Request("https://commons.wikimedia.org/w/api.php?" + q, headers=UA), timeout=30) as r:
        p = json.load(r)["query"]["pages"][0]
    ii = (p.get("imageinfo") or [None])[0]
    if p.get("missing") or not ii:
        return None
    em = ii.get("extmetadata", {})
    art = re.sub(r"<[^>]+>", "", em.get("Artist", {}).get("value", "")).strip()
    return {"title": p["title"].replace("File:", ""), "mime": ii.get("mime", ""), "w": ii.get("width", 0), "h": ii.get("height", 0),
            "thumb": ii.get("thumburl") or ii.get("url"), "page": ii.get("descriptionurl"),
            "lic": em.get("LicenseShortName", {}).get("value", ""), "art": re.sub(r"\s+", " ", art)[:80]}


def main():
    mode = sys.argv[1]
    body = os.environ.get("ISSUE_BODY", "")
    dino, raw = field(body, "Dinosaur"), field(body, "Wikimedia Commons file")
    rows = json.loads((ROOT / "data/dinos.json").read_text())
    names = {r["name"].lower(): r for r in rows}
    problems, notes = [], []
    row = names.get(dino.lower())
    if not row:
        problems.append(f"**{dino or '(blank)'}** is not a dinosaur on the site. Use the name exactly as it appears there.")
    f = file_name(raw)
    info = commons(f) if f else None
    if not info:
        problems.append(f"No file called **{f or '(blank)'}** was found on Wikimedia Commons. Upload it with the "
                        "[Upload Wizard](https://commons.wikimedia.org/wiki/Special:UploadWizard) first, then edit this issue.")
    else:
        if info["mime"] not in ("image/jpeg", "image/png", "image/webp"):
            problems.append(f"The file is `{info['mime']}`. Please use a JPEG, PNG or WebP picture.")
        if not FREE.search(info["lic"]) or NOT_FREE.search(info["lic"]):
            problems.append(f"Commons lists the licence as **{info['lic'] or 'unknown'}**. Only CC0, public domain, CC BY and CC BY-SA are accepted.")
        if min(info["w"], info["h"]) < 300:
            problems.append(f"The picture is only {info['w']}×{info['h']} pixels. Please use one at least 300 pixels on the short side.")
    ok = not problems
    out = []
    if info:
        out += [f"![{info['title']}]({info['thumb']})", "",
                f"**Commons file:** [{info['title']}]({info['page']})  ", f"**Licence on Commons:** {info['lic'] or 'unknown'}  ",
                f"**Artist on Commons:** {info['art'] or 'unknown'}  ", f"**Size:** {info['w']}×{info['h']}", ""]
    if mode == "check":
        if ok:
            current = row.get("cfile") or row.get("file")
            out.append(f"✅ Automatic checks passed for **{row['name']}**." +
                       (f" It currently uses [{current}](https://commons.wikimedia.org/wiki/File:{urllib.parse.quote(current.replace(' ', '_'))})." if current else " It has no picture yet."))
            out.append("\nThe site owner will review it. Adding the `image-approved` label puts it on the site.")
        else:
            out.append("⚠️ Some checks did not pass:\n\n" + "\n".join("- " + p for p in problems) +
                       "\n\nYou can edit this issue to fix them; the checks run again.")
    else:  # apply
        if ok:
            ov_p, cl_p = ROOT / "scripts/overrides.json", ROOT / "scripts/clear_picks.json"
            ov = json.loads(ov_p.read_text())
            ov.setdefault(row["name"], {})
            for k in ("img", "file", "art", "lic"):
                ov[row["name"]].pop(k, None)
            ov[row["name"]]["pick"] = info["title"]
            ov_p.write_text(json.dumps(dict(sorted(ov.items())), ensure_ascii=False, indent=1) + "\n")
            if cl_p.exists():
                cl = json.loads(cl_p.read_text())
                if cl.pop(row["name"], None) is not None:
                    cl_p.write_text(json.dumps(dict(sorted(cl.items())), ensure_ascii=False, indent=1) + "\n")
            ban = ROOT / "scripts/banned_images.txt"
            if ban.exists():
                lines = [l for l in ban.read_text().splitlines() if l.strip() != info["title"]]
                ban.write_text("\n".join(lines) + "\n")
            out.append(f"🦖 Approved. **{row['name']}** will use this picture once the data rebuild finishes (about 10 minutes). Thank you!")
            Path("dino.txt").write_text(row["name"])
        else:
            out.append("Could not apply this submission:\n\n" + "\n".join("- " + p for p in problems))
    Path("comment.md").write_text("\n".join(out) + "\n")
    print(f"ok={'true' if ok else 'false'}")


main()
