#!/usr/bin/env python3
"""Find life restorations with a clear (transparent or plain) background.

For every dinosaur in data/dinos.json this gathers candidate pictures from
Wikimedia Commons, downloads a small thumbnail of each, and measures how plain
the border of the picture is. The best three per dinosaur go to
data/clear_candidates.json, and review sheets go to review/ so a person can
weed out skeletal diagrams, which also have plain backgrounds.

Runs on GitHub Actions (see .github/workflows/find-clear.yml).
"""
import io, json, re, sys, time, pathlib, urllib.parse, urllib.request
from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
UA = "MesozoicCarousel/1.0 (https://github.com/sayantandatta/mesozoic-carousel)"
CM = "https://commons.wikimedia.org/w/api.php"
BAD = re.compile(r"skull|skelet|size|bone|fossil|tooth|teeth|mount|holotype|specimen|scale|track|footprint|\bcast\b|museum|museo|jaw|claw|vertebr|diagram|statue|sculpture|park|exhibit|\btoy|stamp|\begg|nest|comparison|silhouette|outline|\bBW\b|black|NHM|AMNH|Senckenberg|display|Tyrrell|Jurassic World|dinopark|Dinosaurier|life-size|replica|robot|model|figure|portrait|bust|close-?up|\bhand|\bfoot|\bfeet|\barm\b|\bleg\b|\btail\b|map\b|phylogen|cladogram|chart|quarry|excavat|locality|formation|endocast|brain|pelvis|femur|manus|\bpes\b|sacrum|bite|lesion|patholog|growth|ontogen|\.svg|\.tif|\.gif|\.webm|\.ogv|\.ogg|\.pdf|\.djvu|1[89]\d\d|Knight|Owen|Marsh|Mantell|skeletal|reconstruction of the skull|head", re.I)
GOOD = re.compile(r"restor|reconstr|\blife\b|flesh|paleoart|palaeoart|\bNT\b|durbed|steveoc|bonadonna|paleocolour|paleogeek|parker|martyniuk|jconway|wierum|abelov|belov|connolly|willoughby|tamura|PaleoNeolitic|TotalDino|\bTD\b|Conty|Sauroarchive|Ashbridge|mortimer|lida|transparent|white background|nomargin", re.I)
FREE = re.compile(r"^(CC BY|CC BY-SA|CC0|Public domain|PD)", re.I)


def api(**p):
    p.update(format="json", formatversion="2")
    url = CM + "?" + urllib.parse.urlencode(p)
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.load(r)
        except Exception:
            time.sleep(2 + attempt * 3)
    return {}


def fetch(url):
    for attempt in range(6):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(3 + attempt * 6 if e.code == 429 else 2 + attempt * 2)
        except Exception:
            time.sleep(2 + attempt * 2)
    return None


def chunks(xs, n):
    for i in range(0, len(xs), n):
        yield xs[i:i + n]


rows = json.loads((ROOT / "data/dinos.json").read_text())
banned = {l.strip() for l in (ROOT / "scripts/banned_images.txt").read_text().splitlines() if l.strip() and not l.startswith("#")}

# ---------- 1. candidates ----------
cands = {}
for r in rows:
    name = r["name"]
    key = name.lower()[:min(7, len(name))]
    found = []
    for f in [r.get("file")] + (r.get("alts") or []):
        if f and f not in found:
            found.append(f)
    for q in (f'intitle:"{name}" transparent', f'intitle:"{name}" filemime:image/png', f'intitle:"{name}" TD',
              f'intitle:"{name}" "white background"', f'intitle:"{name}" restoration'):
        j = api(action="query", list="search", srsearch=q + " filetype:bitmap", srnamespace=6, srlimit=8)
        for x in j.get("query", {}).get("search", []):
            if re.search(r"inaccura|outdated|disputed|obsolete", x.get("snippet", ""), re.I):
                continue
            t = x["title"].replace("File:", "")
            if key in t.lower() and t not in found:
                found.append(t)
        time.sleep(0.1)
    cands[name] = [f for f in found if f not in banned and not BAD.search(f)][:10]
print("candidates gathered", sum(len(v) for v in cands.values()), file=sys.stderr)

# ---------- 2. image info ----------
info = {}
files = sorted({f for v in cands.values() for f in v})
for ch in chunks(files, 40):
    j = api(action="query", titles="|".join("File:" + f for f in ch), prop="imageinfo",
            iiprop="url|size|extmetadata|mime", iiurlwidth=120, iiextmetadatafilter="Artist|LicenseShortName")
    q = j.get("query", {})
    norm = {x["to"]: x["from"] for x in q.get("normalized", [])}
    for p in q.get("pages", []):
        ii = (p.get("imageinfo") or [None])[0]
        if not ii:
            continue
        em = ii.get("extmetadata", {})
        art = re.sub(r"<[^>]+>", "", em.get("Artist", {}).get("value", ""))
        art = re.split(r"\s*\|\s*|\s*https?://|\s*\(|\s*<", re.sub(r"\s+", " ", art).strip())[0].replace("©", "").strip()[:60]
        full = ii.get("url", "")
        big = ii["thumburl"].replace("/120px-", "/960px-") if ii.get("width", 0) > 960 and ii.get("thumburl") else full
        info[norm.get(p["title"], p["title"]).replace("File:", "")] = {
            "thumb": (ii.get("thumburl") or full).split("?")[0], "url": big.split("?")[0], "w": ii.get("width", 0), "h": ii.get("height", 0),
            "mime": ii.get("mime", ""), "lic": em.get("LicenseShortName", {}).get("value", ""), "art": art}
    time.sleep(0.3)


# ---------- 3. measure the background ----------
def measure(img):
    im = img.convert("RGBA")
    im.thumbnail((120, 120))
    w, h = im.size
    px = im.load()
    b = max(2, int(min(w, h) * 0.07))
    border = [px[x, y] for x in range(w) for y in range(h) if x < b or y < b or x >= w - b or y >= h - b]
    trans = [p for p in border if p[3] < 24]
    opaque = [p for p in border if p[3] >= 24]
    if opaque:
        med = tuple(sorted(c[i] for c in opaque)[len(opaque) // 2] for i in range(3))
        near = sum(1 for p in opaque if sum((p[i] - med[i]) ** 2 for i in range(3)) <= 26 ** 2)
    else:
        med, near = (255, 255, 255), 0
    clear = (len(trans) + near) / len(border)
    kind = "transparent" if len(trans) / len(border) > 0.6 else "plain"
    light = kind == "transparent" or sum(med) / 3 >= 165
    # how much of the picture is the animal (not background)
    allpx = [px[x, y] for x in range(w) for y in range(h)]
    subj = sum(1 for p in allpx if p[3] >= 24 and sum((p[i] - med[i]) ** 2 for i in range(3)) > 45 ** 2) / len(allpx)
    return clear, kind, light, subj, med


out, sheet_rows = {}, []
for n, (name, fs) in enumerate(cands.items()):
    scored = []
    for k, f in enumerate(fs):
        i = info.get(f)
        if not i or not FREE.search(i["lic"] or "") or i["w"] < 300 or i["mime"] not in ("image/jpeg", "image/png", "image/webp"):
            continue
        data = fetch(i["thumb"])
        time.sleep(0.12)
        if not data:
            continue
        try:
            img = Image.open(io.BytesIO(data))
            clear, kind, light, subj, med = measure(img)
        except Exception:
            continue
        if clear < 0.9 or not (0.05 <= subj <= 0.8):
            continue
        score = clear + (0.08 if light else 0) + (0.1 if GOOD.search(f) else 0) - k * 0.01
        scored.append((score, f, kind, light, img))
    scored.sort(key=lambda s: -s[0])
    top = scored[:3]
    if top:
        out[name] = [{"file": f, "url": info[f]["url"], "art": info[f]["art"], "lic": info[f]["lic"], "kind": kind, "light": light}
                     for _, f, kind, light, _ in top]
        sheet_rows.append((name, [(f, kind, img) for _, f, kind, _, img in top]))
    if n % 50 == 0:
        print(f"{n}/{len(cands)} measured, {len(out)} with clear pictures", file=sys.stderr)

(ROOT / "data/clear_candidates.json").write_text(json.dumps(out, ensure_ascii=False, indent=0))
print(f"clear pictures found for {len(out)} of {len(rows)} dinosaurs", file=sys.stderr)

# ---------- 4. review sheets ----------
rev = ROOT / "review"
rev.mkdir(exist_ok=True)
for old in rev.glob("*.png"):
    old.unlink()
try:
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 15)
    small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
except Exception:
    font = small = ImageFont.load_default()
CELL_W, CELL_H, LABEL_W, ROWS, COLS = 190, 130, 170, 13, 2
COL_W = LABEL_W + 3 * CELL_W
for s, chunk in enumerate(chunks(sheet_rows, ROWS * COLS)):
    sheet = Image.new("RGB", (COL_W * COLS + 10, ROWS * CELL_H + 10), (60, 60, 60))
    d = ImageDraw.Draw(sheet)
    for k, (name, imgs) in enumerate(chunk):
        x0 = 5 + (k // ROWS) * COL_W
        y0 = 5 + (k % ROWS) * CELL_H
        d.rectangle([x0, y0, x0 + LABEL_W - 4, y0 + CELL_H - 4], fill=(255, 250, 220))
        d.text((x0 + 6, y0 + 6), f"{s * ROWS * COLS + k}", font=small, fill=(90, 90, 90))
        d.text((x0 + 6, y0 + 24), name[:17], font=font, fill=(0, 0, 0))
        if len(name) > 17:
            d.text((x0 + 6, y0 + 42), name[17:], font=font, fill=(0, 0, 0))
        for j, (f, kind, img) in enumerate(imgs):
            cx = x0 + LABEL_W + j * CELL_W
            d.rectangle([cx, y0, cx + CELL_W - 4, y0 + CELL_H - 4], fill=(200, 205, 200))
            im = img.convert("RGBA")
            im.thumbnail((CELL_W - 10, CELL_H - 22))
            sheet.paste(im, (cx + 3 + (CELL_W - 10 - im.width) // 2, y0 + 3), im)
            d.text((cx + 4, y0 + CELL_H - 20), f"{j + 1} {'T' if kind == 'transparent' else 'P'}", font=small, fill=(0, 0, 0))
    sheet.save(rev / f"sheet-{s:02d}.png", optimize=True)
print("review sheets written", file=sys.stderr)
