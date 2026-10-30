"""Check an image submission issue, and apply it when approved.

Usage: python scripts/check_image.py check|apply
Reads the issue from $ISSUE_BODY and $ISSUE_URL. Writes a Markdown comment to comment.md
and prints ok=true/false for GitHub Actions.

A submission is either a Wikimedia Commons file, or a picture uploaded into the issue
(GitHub attachment). Approved Commons files go into scripts/overrides.json as a "pick".
Approved uploads are resized, stripped of metadata and stored in images/submitted/,
and recorded in scripts/submitted_images.json.
"""
import io, json, os, re, sys, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIVE = "https://sayantandatta.github.io/mesozoic-carousel/"
FREE = re.compile(r"^(cc0|cc-?zero|public domain|pd\b|pd-|no restrictions|cc[ -]by(-sa)?[ -]\d)", re.I)
NOT_FREE = re.compile(r"\b(nc|nd)\b|non-?commercial|no-?deriv", re.I)
UPLOAD_FREE = re.compile(r"^(cc0( 1\.0)?|public domain|cc[ -]by 4\.0|cc[ -]by-sa 4\.0)$", re.I)
ATTACH = re.compile(r"https://(?:github\.com/user-attachments/assets/[0-9a-fA-F-]{20,}"
                    r"|user-images\.githubusercontent\.com/[\w./%-]+?\.(?:png|jpe?g|webp)"
                    r"|github\.com/[\w.-]+/[\w.-]+/assets/\d+/[0-9a-fA-F-]{20,})")
UA = {"User-Agent": "MesozoicCarousel/1.0 (https://github.com/sayantandatta/mesozoic-carousel)"}
MAX_BYTES, MIN_SIDE, MAX_SIDE = 10 * 1024 * 1024, 300, 1600
SUBMITTED = ROOT / "scripts/submitted_images.json"


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


def download(url):
    """Fetch a GitHub attachment. The token is only sent to github.com, never to the redirect target."""
    req = urllib.request.Request(url, headers=UA)
    tok = os.environ.get("GH_TOKEN")
    if tok and url.startswith("https://github.com/"):
        req.add_unredirected_header("Authorization", "token " + tok)
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read(MAX_BYTES + 1)
    return data


def open_upload(data):
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = 60_000_000
    im = Image.open(io.BytesIO(data))
    fmt = im.format
    im.load()
    return im, fmt


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def save_upload(im, name):
    """Resize, drop all metadata (EXIF, GPS, comments) and save. Transparent pictures stay PNG."""
    from PIL import Image, ImageOps
    im = ImageOps.exif_transpose(im)
    alpha = im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info)
    im = im.convert("RGBA" if alpha else "RGB")
    if alpha and im.getchannel("A").getextrema()[0] == 255:
        im, alpha = im.convert("RGB"), False
    k = min(1.0, MAX_SIDE / max(im.size))
    if k < 1:
        im = im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)
    clean = Image.frombytes(im.mode, im.size, im.tobytes())   # a fresh image carries no metadata
    out = ROOT / "images/submitted"
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob(slug(name) + ".*"):
        old.unlink()
    path = out / (slug(name) + (".png" if alpha else ".webp"))
    if alpha:
        clean.save(path, "PNG", optimize=True)
    else:
        clean.save(path, "WEBP", quality=86, method=6)
    return path.relative_to(ROOT).as_posix(), clean.size


def drop_submitted(name):
    if not SUBMITTED.exists():
        return
    sub = json.loads(SUBMITTED.read_text())
    old = sub.pop(name, None)
    if old:
        p = ROOT / old["path"]
        if p.exists():
            p.unlink()
        SUBMITTED.write_text(json.dumps(dict(sorted(sub.items())), ensure_ascii=False, indent=1) + "\n")


def drop_clear(name):
    cl_p = ROOT / "scripts/clear_picks.json"
    if cl_p.exists():
        cl = json.loads(cl_p.read_text())
        if cl.pop(name, None) is not None:
            cl_p.write_text(json.dumps(dict(sorted(cl.items())), ensure_ascii=False, indent=1) + "\n")


def main():
    mode = sys.argv[1]
    body = os.environ.get("ISSUE_BODY", "")
    issue_url = os.environ.get("ISSUE_URL", "")
    dino, raw = field(body, "Dinosaur"), field(body, "Wikimedia Commons file")
    upload_field = field(body, "Picture file")
    artist, licence = field(body, "Artist or credit line"), field(body, "Licence")
    rows = json.loads((ROOT / "data/dinos.json").read_text())
    row = {r["name"].lower(): r for r in rows}.get(dino.lower())
    problems, out = [], []
    if not row:
        problems.append(f"**{dino or '(blank)'}** is not a dinosaur on the site. Use the name exactly as it appears there.")

    f = file_name(raw)
    attach = ATTACH.findall(upload_field)
    info = up = None
    if f:
        source = "commons"
        info = commons(f)
        if not info:
            problems.append(f"No file called **{f}** was found on Wikimedia Commons. Check the name, or leave it blank and "
                            "paste the picture into **Picture file** instead.")
        else:
            if info["mime"] not in ("image/jpeg", "image/png", "image/webp"):
                problems.append(f"The file is `{info['mime']}`. Please use a JPEG, PNG or WebP picture.")
            if not FREE.search(info["lic"]) or NOT_FREE.search(info["lic"]):
                problems.append(f"Commons lists the licence as **{info['lic'] or 'unknown'}**. Only CC0, public domain, CC BY and CC BY-SA are accepted.")
            if min(info["w"], info["h"]) < MIN_SIDE:
                problems.append(f"The picture is only {info['w']}×{info['h']} pixels. Please use one at least {MIN_SIDE} pixels on the short side.")
            out += [f"![{info['title']}]({info['thumb']})", "",
                    f"**Commons file:** [{info['title']}]({info['page']})  ", f"**Licence on Commons:** {info['lic'] or 'unknown'}  ",
                    f"**Artist on Commons:** {info['art'] or 'unknown'}  ", f"**Size:** {info['w']}×{info['h']}", ""]
    elif attach:
        source = "upload"
        if len(set(attach)) > 1:
            out.append(f"More than one picture is attached; the first one is used.\n")
        try:
            data = download(attach[0])
            if len(data) > MAX_BYTES:
                raise ValueError("too big")
            im, fmt = open_upload(data)
            up = {"im": im, "fmt": fmt, "bytes": len(data)}
            if fmt not in ("JPEG", "PNG", "WEBP"):
                problems.append(f"The picture is a {fmt or 'unknown'} file. Please use a JPEG, PNG or WebP picture.")
            if min(im.size) < MIN_SIDE:
                problems.append(f"The picture is only {im.width}×{im.height} pixels. Please use one at least {MIN_SIDE} pixels on the short side.")
            out += [f"**Uploaded picture:** {im.width}×{im.height} {fmt}, {len(data) / 1048576:.1f} MB  "]
        except ValueError:
            problems.append("The picture is larger than 10 MB. Please use a smaller file.")
        except Exception as e:  # noqa: BLE001 - report anything that stops the download or decode
            problems.append(f"The uploaded picture couldn't be opened ({type(e).__name__}). Try pasting it again, as a JPEG, PNG or WebP file.")
        if not UPLOAD_FREE.match(licence.strip()):
            problems.append(f"For uploaded pictures the licence must be CC0 1.0, Public domain, CC BY 4.0 or CC BY-SA 4.0 (you wrote **{licence or 'nothing'}**).")
        if not artist.strip():
            problems.append("Please add the artist or credit line.")
        out += [f"**Licence (declared):** {licence or 'none'}  ", f"**Artist:** {artist or 'none'}", ""]
    else:
        source = None
        problems.append("No picture was found. Give a Wikimedia Commons file, or paste or drag the picture into **Picture file** "
                        "and wait for its link to appear before saving.")

    ok = not problems
    if mode == "check":
        if ok:
            current = row.get("cfile") or row.get("file")
            cur = (f" It currently uses {current}." if current else " It has no picture yet.")
            out.append(f"✅ Automatic checks passed for **{row['name']}**.{cur}")
            out.append("\nThe site owner will review it. Adding the `image-approved` label puts it on the site.")
        else:
            out.append("⚠️ Some checks did not pass:\n\n" + "\n".join("- " + p for p in problems) +
                       "\n\nYou can edit this issue to fix them; the checks run again.")
    else:  # apply
        if ok and source == "commons":
            ov_p = ROOT / "scripts/overrides.json"
            ov = json.loads(ov_p.read_text())
            ov.setdefault(row["name"], {})
            for k in ("img", "file", "art", "lic"):
                ov[row["name"]].pop(k, None)
            ov[row["name"]]["pick"] = info["title"]
            ov_p.write_text(json.dumps(dict(sorted(ov.items())), ensure_ascii=False, indent=1) + "\n")
            drop_clear(row["name"])
            drop_submitted(row["name"])
            ban = ROOT / "scripts/banned_images.txt"
            if ban.exists():
                ban.write_text("\n".join(l for l in ban.read_text().splitlines() if l.strip() != info["title"]) + "\n")
        elif ok and source == "upload":
            drop_submitted(row["name"])
            path, size = save_upload(up["im"], row["name"])
            sub = json.loads(SUBMITTED.read_text()) if SUBMITTED.exists() else {}
            sub[row["name"]] = {"path": path, "url": LIVE + path, "art": artist.strip()[:80], "lic": licence.strip(), "src": issue_url}
            SUBMITTED.write_text(json.dumps(dict(sorted(sub.items())), ensure_ascii=False, indent=1) + "\n")
            drop_clear(row["name"])
            out.append(f"Saved as `{path}` ({size[0]}×{size[1]}), with photo metadata removed.\n")
        if ok:
            out.append(f"🦖 Approved. **{row['name']}** will use this picture once the data rebuild finishes (about 10 minutes). Thank you!")
            Path("dino.txt").write_text(row["name"])
        else:
            out.append("Could not apply this submission:\n\n" + "\n".join("- " + p for p in problems))
    Path("comment.md").write_text("\n".join(out) + "\n")
    print(f"ok={'true' if ok else 'false'}")


if __name__ == "__main__":
    main()
