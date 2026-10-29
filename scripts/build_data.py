#!/usr/bin/env python3
"""Build data/dinos.json for Mesozoic Carousel.

For every name in scripts/names.txt this looks up the Wikipedia article,
reads the period, age and length from its introduction, works out the
animal's group (and so its diet), and picks a freely licensed life
restoration from Wikimedia Commons.

Runs on GitHub Actions (see .github/workflows/build-data.yml).
"""
import json, os, re, sys, time, pathlib, urllib.parse, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
UA = "MesozoicCarousel/1.0 (https://github.com/sayantandatta/mesozoic-carousel)"
WP = "https://en.wikipedia.org/w/api.php"
CM = "https://commons.wikimedia.org/w/api.php"
WD = "https://www.wikidata.org/w/api.php"


def api(base, **p):
    p.update(format="json", formatversion="2")
    url = base + "?" + urllib.parse.urlencode(p)
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.load(r)
        except Exception as e:  # rate limit or network blip
            time.sleep(2 + attempt * 3)
    print("FAILED", url[:160], file=sys.stderr)
    return {}


def chunks(xs, n):
    for i in range(0, len(xs), n):
        yield xs[i:i + n]


OFFLINE = "--offline" in sys.argv          # re-run classification from data/raw.json only
REUSE_IMAGES = OFFLINE or os.environ.get("REUSE_IMAGES") == "1"
RAW = ROOT / "data/raw.json"
PREV = {r["name"]: r for r in json.loads((ROOT / "data/dinos.json").read_text())} if (ROOT / "data/dinos.json").exists() else {}

# ---------- 1. find the right Wikipedia article ----------
names = [n.strip() for n in (ROOT / "scripts/names.txt").read_text().splitlines() if n.strip()]
SPECIAL = {"Yi": "Yi (dinosaur)"}
DINO_WORDS = re.compile(r"dinosaur|sauropod|theropod|ornithopod|ceratops|saur|archosaur|synapsid|pterosaur|bird", re.I)


def resolve(titles):
    """Return {asked: (final_title, exists)} following redirects."""
    out = {}
    for ch in chunks(titles, 50):
        j = api(WP, action="query", titles="|".join(ch), redirects=1, prop="pageprops", ppprop="disambiguation")
        q = j.get("query", {})
        norm = {x["from"]: x["to"] for x in q.get("normalized", [])}
        red = {x["from"]: x["to"] for x in q.get("redirects", [])}
        pages = {p["title"]: p for p in q.get("pages", [])}
        for t in ch:
            f = norm.get(t, t)
            f = red.get(f, f)
            p = pages.get(f, {})
            ok = not p.get("missing") and not p.get("invalid") and "disambiguation" not in p.get("pageprops", {})
            out[t] = (f, ok)
        time.sleep(0.3)
    return out


def fetch_articles():
    cand_dino = resolve([SPECIAL.get(n, f"{n} (dinosaur)") for n in names])
    cand_plain = resolve(names)
    title_for = {}
    for n in names:
        a = cand_dino[SPECIAL.get(n, f"{n} (dinosaur)")]
        b = cand_plain[n]
        t = a[0] if a[1] else (b[0] if b[1] else None)
        title_for[n] = None if (t and t.startswith("List of")) else t

    # ---------- 2. read each article's introduction and image list ----------
    intro, article_images = {}, {}
    titles = sorted({t for t in title_for.values() if t})
    for ch in chunks(titles, 20):
        cont = {}
        while True:
            j = api(WP, action="query", titles="|".join(ch), prop="extracts", exintro=1, explaintext=1, exlimit=20, **cont)
            for p in j.get("query", {}).get("pages", []):
                if p.get("extract"):
                    intro[p["title"]] = p["extract"]
            if "continue" not in j:
                break
            cont = j["continue"]
            time.sleep(0.2)
        time.sleep(0.3)
    for ch in chunks(titles, 20):
        cont = {}
        while True:
            j = api(WP, action="query", titles="|".join(ch), prop="images", imlimit=500, **cont)
            for p in j.get("query", {}).get("pages", []):
                article_images.setdefault(p["title"], []).extend(i["title"] for i in p.get("images", []))
            if "continue" not in j:
                break
            cont = j["continue"]
        time.sleep(0.3)
    RAW.write_text(json.dumps({"titles": title_for, "intro": intro, "images": article_images}, ensure_ascii=False))
    return title_for, intro, article_images


if OFFLINE:
    raw = json.loads(RAW.read_text())
    title_for, intro, article_images = raw["titles"], raw["intro"], raw["images"]
else:
    title_for, intro, article_images = fetch_articles()

# ---------- 3. facts from the introduction ----------
STAGES = {  # ICS 2023 ages, million years ago
    "Maastrichtian": (72.1, 66.0, "Late Cretaceous"), "Campanian": (83.6, 72.1, "Late Cretaceous"),
    "Santonian": (86.3, 83.6, "Late Cretaceous"), "Coniacian": (89.8, 86.3, "Late Cretaceous"),
    "Turonian": (93.9, 89.8, "Late Cretaceous"), "Cenomanian": (100.5, 93.9, "Late Cretaceous"),
    "Albian": (113.0, 100.5, "Early Cretaceous"), "Aptian": (121.4, 113.0, "Early Cretaceous"),
    "Barremian": (125.8, 121.4, "Early Cretaceous"), "Hauterivian": (132.6, 125.8, "Early Cretaceous"),
    "Valanginian": (139.8, 132.6, "Early Cretaceous"), "Berriasian": (145.0, 139.8, "Early Cretaceous"),
    "Tithonian": (149.2, 145.0, "Late Jurassic"), "Kimmeridgian": (154.8, 149.2, "Late Jurassic"),
    "Oxfordian": (161.5, 154.8, "Late Jurassic"), "Callovian": (165.3, 161.5, "Middle Jurassic"),
    "Bathonian": (168.2, 165.3, "Middle Jurassic"), "Bajocian": (170.9, 168.2, "Middle Jurassic"),
    "Aalenian": (174.7, 170.9, "Middle Jurassic"), "Toarcian": (184.2, 174.7, "Early Jurassic"),
    "Pliensbachian": (192.9, 184.2, "Early Jurassic"), "Sinemurian": (199.5, 192.9, "Early Jurassic"),
    "Hettangian": (201.4, 199.5, "Early Jurassic"), "Rhaetian": (208.5, 201.4, "Late Triassic"),
    "Norian": (227.0, 208.5, "Late Triassic"), "Carnian": (237.0, 227.0, "Late Triassic"),
    "Ladinian": (242.0, 237.0, "Middle Triassic"), "Anisian": (247.2, 242.0, "Middle Triassic"),
}
PERIODS = {
    "Late Cretaceous": (100.5, 66.0), "Early Cretaceous": (145.0, 100.5),
    "Late Jurassic": (161.5, 145.0), "Middle Jurassic": (174.7, 161.5), "Early Jurassic": (201.4, 174.7),
    "Late Triassic": (237.0, 201.4), "Middle Triassic": (247.2, 237.0), "Early Permian": (298.9, 273.0),
}
NUM = r"(\d{2,3}(?:\.\d+)?)"


def facts(text):
    t = text.replace("–", "-").replace("—", "-").replace(" ", " ")
    t = re.sub(r"\s+", " ", t)
    period = None
    m = re.search(r"\b(Early|Middle|Late|Lower|Upper)\s+(Triassic|Jurassic|Cretaceous|Permian)\b", t)
    if m:
        period = {"Lower": "Early", "Upper": "Late"}.get(m.group(1), m.group(1)) + " " + m.group(2)
    ma = None
    m = re.search(NUM + r"\s*(?:-|to|and)\s*" + NUM + r"\s*(?:million years|mya|Ma\b)", t)
    if m:
        a, b = float(m.group(1)), float(m.group(2))
        if 60 <= min(a, b) and max(a, b) <= 300:
            ma = [max(a, b), min(a, b)]
    if not ma:
        m = re.search(NUM + r"\s*(?:million years ago|mya|Ma\b)", t)
        if m and 60 <= float(m.group(1)) <= 300:
            v = float(m.group(1)); ma = [v, v]
    stage = None
    for s in STAGES:
        if re.search(r"\b" + s, t):
            stage = s; break
    if not ma and stage:
        ma = list(STAGES[stage][:2])
    if not period and stage:
        period = STAGES[stage][2]
    if not period and ma:
        for p, (a, b) in PERIODS.items():
            if b <= ma[0] <= a:
                period = p; break
    if not period:
        m = re.search(r"\b(Triassic|Jurassic|Cretaceous)\b", t)
        if m:
            period = m.group(1)
    if not ma and period in PERIODS:
        ma = list(PERIODS[period])
    if not ma and period in ("Triassic", "Jurassic", "Cretaceous"):
        ma = {"Triassic": [237.0, 201.4], "Jurassic": [201.4, 145.0], "Cretaceous": [145.0, 66.0]}[period]
    if ma:
        ma = [round(ma[0]), round(ma[1])]
    length = None
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:-|to)?\s*(\d+(?:\.\d+)?)?\s*(m|metres|meters|cm|centimetres|centimeters)\b[^.]{0,40}?\b(long|in length|length)", t) \
        or re.search(r"\b(?:length|long)\b[^.]{0,40}?(\d+(?:\.\d+)?)\s*(?:-|to)?\s*(\d+(?:\.\d+)?)?\s*(m|metres|meters|cm|centimetres|centimeters)\b", t)
    if m:
        hi = float(m.group(2) or m.group(1))
        if m.group(3).startswith("c"):
            hi /= 100
        if 0.1 <= hi <= 45:
            length = (f"{hi:.1f}".rstrip("0").rstrip(".")) + " m"
    return period, ma, length


# ---------- 4. group, diet and drawing template ----------
GROUPS = [  # (pattern, group, diet, template, what it ate). Family words only, never genus names.
    (r"synapsids?\b|pelycosaur|sphenacodont", "synapsid", "carn", "spino", "meat, including fish, amphibians and other reptiles"),
    (r"plesiosaur(?:s|ian)?\b", "marine", "carn", "spino", "fish and other sea animals"),
    (r"spinosaurids?\b|spinosaurines?\b|baryonychines?\b|spinosauroids?\b", "spinosaur", "carn", "spino", "mostly fish, plus other animals it caught near the water"),
    (r"tyrannosaur(?:id|oid|ine|s)?\b", "tyrannosaur", "carn", "trex", "meat, mostly other dinosaurs"),
    (r"therizinosaur(?:id|oid|ian|s)?\b|segnosaur(?:id|ian|s)\b", "therizinosaur", "herb", "galli", "leaves, pulled down from trees with its long claws"),
    (r"oviraptor(?:id|ids|osaur|osaurs|osaurian|ine)\b|caenagnathids?\b", "oviraptorosaur", "omni", "galli", "plants and seeds, and possibly eggs and small animals"),
    (r"ornithomim(?:id|ids|osaur|osaurs|osaurian|ine)\b|deinocheirids?\b", "ornithomimosaur", "omni", "galli", "plants, seeds, insects and small animals"),
    (r"alvarezsaur(?:id|ids|oid|oids|s)?\b", "alvarezsaur", "carn", "compy", "insects such as ants and termites"),
    (r"troodont(?:id|ids|s)?\b", "troodontid", "omni", "velo", "small animals, insects and possibly plants"),
    (r"dromaeosaur(?:id|ids|ine|s)?\b|\braptors?\b|unenlagiines?\b|microraptorines?\b|eudromaeosaur", "dromaeosaur", "carn", "velo", "small and medium-sized animals, gripped with its sickle-shaped foot claws"),
    (r"ceratopsians?\b|ceratopsids?\b|ceratopsia\b|chasmosaurines?\b|centrosaurines?\b|leptoceratopsids?\b|protoceratopsids?\b|psittacosaurids?\b|horned dinosaur|frilled dinosaur", "ceratopsian", "herb", "tri", "tough, low-growing plants, sliced with its sharp beak"),
    (r"ankylosaur(?:id|ids|ian|ians|ine|ines|s)?\b|nodosaur(?:id|ids|ine|s)?\b|armou?red dinosaur|thyreophoran", "ankylosaur", "herb", "anky", "low ferns and other leafy plants"),
    (r"stegosaur(?:id|ids|ian|ians|s)?\b", "stegosaur", "herb", "steg", "ferns, mosses and other low plants"),
    (r"pachycephalosaur(?:id|ids|ian|ians|ine|s)?\b|bone-headed|dome-headed|thick-headed", "pachycephalosaur", "herb", "pachy", "leaves, seeds and fruit"),
    (r"lambeosaurines?\b", "hadrosaur", "herb", "para", "leaves, twigs and conifer needles, ground up by hundreds of teeth"),
    (r"hadrosaur(?:id|ids|oid|oids|ine|s|iform|iforms|omorph|omorphs|omorphan)?\b|saurolophines?\b|duck-?billed", "hadrosaur", "herb", "igu", "leaves, twigs and conifer needles, ground up by hundreds of teeth"),
    (r"heterodontosaur(?:id|ids|s)?\b", "heterodontosaur", "omni", "compy", "plants, and maybe insects and small animals"),
    (r"iguanodont(?:ian|ians|id|ids|s)?\b|ornithopods?\b|hypsilophodont(?:id|ids)?\b|rhabdodontids?\b|ornithischians?\b|thescelosaurids?\b|dryosaurids?\b|elasmarians?\b|neornithischian", "ornithopod", "herb", "igu", "low-growing plants such as ferns and horsetails"),
    (r"brachiosaur(?:id|ids|s)?\b", "sauropod", "herb", "brach", "leaves from the tops of tall trees"),
    (r"prosauropods?\b|sauropodomorphs?\b|sauropodiforms?\b|plateosaurids?\b|massospondylids?\b|anchisaurids?\b", "sauropodomorph", "herb", "igu", "leaves and other plants, and perhaps the odd small animal"),
    (r"titanosaur(?:id|ids|ian|ians|iform|s)?\b|sauropods?\b|diplodocids?\b|diplodocoids?\b|macronarians?\b|camarasaurids?\b|mamenchisaurids?\b|rebbachisaurids?\b|dicraeosaurids?\b|turiasaurs?\b|eusauropods?\b|neosauropods?\b|somphospondyl|euhelopodids?\b|cetiosaurids?\b|apatosaurines?\b", "sauropod", "herb", "diplo", "leaves from tall trees and other plants, swallowed without chewing"),
    (r"coelophysoids?\b|coelophysids?\b|herrerasaur(?:id|ids|ian|ians)\b|compsognathids?\b|dilophosaurids?\b", "theropod", "carn", "coelo", "small animals such as lizards and insects"),
    (r"abelisaur(?:id|ids|oid|oids|ine)?\b|carcharodontosaur(?:id|ids|ian|s)?\b|allosaur(?:id|ids|oid|oids|s)?\b|megalosaur(?:id|ids|oid|oids|s)?\b|ceratosaur(?:id|ids|ian|ians|s)?\b|metriacanthosaurids?\b|sinraptorids?\b|megaraptor(?:an|ans|id|ids)\b|noasaurids?\b|tetanurans?\b|theropods?\b|carnosaur(?:s|ian|ians)?\b|piatnitzkysaurids?\b|coelurosaur(?:s|ian|ians)?\b|maniraptor", "theropod", "carn", "allo", "meat, hunting other animals"),
    (r"avialans?\b|avialae\b|scansoriopterygids?\b|paravians?\b|\bbirds?\b", "avialan", "carn", "compy", "insects and other small animals"),
    (r"dinosauromorphs?\b|dinosauriforms?\b|silesaurids?\b|pseudosuchians?\b|crocodylomorphs?\b|archosaurs?\b", "archosaur", "carn", "coelo", "small animals"),
]
SMALL_THEROPOD_EATS = "small animals such as lizards, insects and early mammals"
BIG_COELO_EATS = "meat, hunting other animals"


def classify(text):
    """The family word that appears first in the article's introduction decides the group."""
    t = text.lower()
    best = None
    for k, (pat, grp, diet, tpl, eats) in enumerate(GROUPS):
        m = re.search(pat, t)
        if m and (best is None or (m.start(), k) < best[0]):
            best = ((m.start(), k), (grp, diet, tpl, eats))
    return best[1] if best else (None, None, None, None)


# ---------- 5. pictures ----------
BAD = re.compile(r"skull|skelet|size|bone|fossil|tooth|teeth|mount|holotype|specimen|scale|track|footprint|\bcast\b|museum|museo|jaw|claw|vertebr|diagram|statue|sculpture|park|exhibit|\btoy|stamp|\begg|nest|comparison|silhouette|outline|\bBW\b|black|NHM|AMNH|Senckenberg|display|Tyrrell|Jurassic World|dinopark|Dinosaurier|life-size|replica|robot|model|figure|portrait|bust|close-?up|\bhand|\bfoot|\bfeet|\barm\b|\bleg\b|\btail\b|map\b|phylogen|cladogram|chart|quarry|excavat|locality|formation|endocast|brain|pelvis|femur|manus|\bpes\b|sacrum|bite|lesion|patholog|growth|ontogen|\.svg|\.tif|\.gif|\.webm|\.ogv|\.ogg|\.pdf|\.djvu|1[89]\d\d|Knight|Owen|Marsh|Mantell", re.I)
GOOD = re.compile(r"restor|reconstr|\blife\b|flesh|paleoart|palaeoart|\bNT\b|durbed|steveoc|bonadonna|paleocolour|paleogeek|parker|martyniuk|jconway|wierum|abelov|belov|connolly|willoughby|tamura|PaleoNeolitic|TotalDino|\bTD\b|Conty|Sauroarchive|Ashbridge|mortimer|lida", re.I)
FREE = re.compile(r"^(CC BY|CC BY-SA|CC0|Public domain|PD)", re.I)


def commons_search(q, n=10):
    j = api(CM, action="query", list="search", srsearch=q, srnamespace=6, srlimit=n)
    return j.get("query", {}).get("search", [])


def pick_image(name, title):
    key = name.lower()[:min(7, len(name))]
    score = {}
    for f in article_images.get(title, []):
        if key in f.lower() and not BAD.search(f):
            score[f] = score.get(f, 0) + (25 if GOOD.search(f) else 4)
    for i, w in enumerate(["restoration", "reconstruction", "life", "paleoart"]):
        for k, x in enumerate(commons_search(f"intitle:{name} {w} filetype:bitmap")):
            f, snip = x["title"], x.get("snippet", "")
            if BAD.search(f) or re.search(r"inaccura|outdated|disputed|obsolete", snip, re.I):
                continue
            if key not in f.lower():
                continue
            score[f] = score.get(f, 0) + 10 - k + (6 if GOOD.search(f) else 0)
        time.sleep(0.15)
    return [f for f, _ in sorted(score.items(), key=lambda kv: -kv[1])][:6]


def image_info(files):
    info = {}
    for ch in chunks(files, 40):
        j = api(CM, action="query", titles="|".join(ch), prop="imageinfo", iiprop="url|size|extmetadata|mime",
                iiurlwidth=960, iiextmetadatafilter="Artist|LicenseShortName|Restrictions")
        q = j.get("query", {})
        norm = {x["to"]: x["from"] for x in q.get("normalized", [])}
        for p in q.get("pages", []):
            ii = (p.get("imageinfo") or [None])[0]
            if not ii:
                continue
            em = ii.get("extmetadata", {})
            art = re.sub(r"<[^>]+>", "", em.get("Artist", {}).get("value", ""))
            art = re.sub(r"\s+", " ", art).strip()
            art = re.split(r"\s*\|\s*|\s*https?://|\s*\(|\s*<", art)[0].replace("©", "").strip()[:60]
            info[norm.get(p["title"], p["title"])] = {
                "w": ii.get("width", 0), "h": ii.get("height", 0), "mime": ii.get("mime", ""),
                "url": ii.get("thumburl") if ii.get("width", 0) > 960 else ii.get("url"),
                "lic": em.get("LicenseShortName", {}).get("value", ""), "art": art,
            }
        time.sleep(0.3)
    return info


# ---------- 6. assemble ----------
rows, seen_titles, cands = [], {}, {}
for n in names:
    t = title_for[n]
    text = intro.get(t, "") if t else ""
    if t and not DINO_WORDS.search(text[:600]):
        t, text = None, ""
    if t and t in seen_titles and seen_titles[t] != n:
        # same animal under another name (e.g. Anatosaurus -> Edmontosaurus): keep the one matching the title
        other = seen_titles[t]
        if n.lower() in t.lower() and other.lower() not in t.lower():
            rows = [r for r in rows if r["name"] != other]
        else:
            print("duplicate", n, "->", t, "(kept", other + ")", file=sys.stderr)
            continue
    if t:
        seen_titles[t] = n
    period, ma, length = facts(text)
    grp, diet, tpl, eats = classify(text)
    if tpl == "allo" and length and float(length.split()[0]) < 3:
        tpl, eats = "coelo", SMALL_THEROPOD_EATS
    elif tpl == "coelo" and grp == "theropod" and length and float(length.split()[0]) >= 3.5:
        eats = BIG_COELO_EATS
    not_dino = bool(re.search(r"not a (true )?dinosaur|synapsid|pelycosaur|plesiosaur|pseudosuchian|crocodylomorph|dinosauriform|dinosauromorph", text[:700], re.I)) \
        and not re.search(r"\bis a (genus|species) of [^.]{0,80}dinosaur", text[:300], re.I)
    rows.append({"name": n, "wiki": t, "period": period, "ma": ma, "len": length, "group": grp,
                 "diet": diet, "tpl": tpl, "eats": eats, "notDino": not_dino})
    if not REUSE_IMAGES:
        cands[n] = pick_image(n, t) if t else pick_image(n, n)

if REUSE_IMAGES:  # keep the pictures chosen last time
    for r in rows:
        p = PREV.get(r["name"], {})
        for k in ("img", "file", "art", "lic", "alts"):
            if k in p:
                r[k] = p[k]
    rows_with_cands = []
else:
    rows_with_cands = rows
all_files = sorted({f for fs in cands.values() for f in fs})
info = image_info(all_files) if all_files else {}
for r in rows_with_cands:
    for f in cands.get(r["name"], []):
        i = info.get(f)
        if not i or not i["url"] or not FREE.search(i["lic"] or "") or i["w"] < 300:
            continue
        if i["mime"] not in ("image/jpeg", "image/png", "image/webp"):
            continue
        r.update(img=i["url"], file=f.replace("File:", ""), art=i["art"], lic=i["lic"])
        break
    r["alts"] = [f.replace("File:", "") for f in cands.get(r["name"], [])][:6]

# hand corrections after review (scripts/overrides.json: {name: {field: value}})
ov_path = ROOT / "scripts/overrides.json"
if ov_path.exists():
    ov = json.loads(ov_path.read_text())
    want = sorted({"File:" + o["pick"] for o in ov.values() if o.get("pick")})
    picked = image_info(want) if (want and not OFFLINE) else {}
    for r in rows:
        for k, v in ov.get(r["name"], {}).items():
            if k == "pick":
                i = picked.get("File:" + v)
                if i and i["url"]:
                    r.update(img=i["url"], file=v, art=i["art"], lic=i["lic"])
                elif OFFLINE and r.get("file") != v:
                    print("pick needs a network run:", r["name"], file=sys.stderr)
                else:
                    print("pick not found:", r["name"], v, file=sys.stderr)
            elif v is None:
                r.pop(k, None)
            else:
                r[k] = v
for r in rows:  # drop tracking parameters from image links
    if r.get("img"):
        r["img"] = r["img"].split("?")[0]

# ---------- 7. family tree from Wikidata (parent taxon chains) ----------
RANKS = {
    "Q34740": "genus", "Q7432": "species", "Q35409": "family", "Q164280": "subfamily", "Q2136103": "superfamily",
    "Q2007442": "infrafamily", "Q227936": "tribe", "Q36602": "order", "Q5867959": "suborder", "Q2889003": "infraorder",
    "Q6311258": "parvorder", "Q5868144": "superorder", "Q37517": "class", "Q713623": "clade", "Q3965313": "subgenus",
}
STOP_AT = {"Dinosauria", "Dinosauromorpha", "Dinosauriformes", "Synapsida", "Sauropterygia", "Plesiosauria",
           "Pseudosuchia", "Archosauria", "Sauropsida", "Reptilia", "Amniota"}


def best_claim(claims, prop):
    st = claims.get(prop, [])
    st = sorted(st, key=lambda c: {"preferred": 0, "normal": 1}.get(c.get("rank"), 2))
    for c in st:
        dv = c.get("mainsnak", {}).get("datavalue", {})
        v = dv.get("value")
        if isinstance(v, dict) and "id" in v:
            return v["id"]
        if isinstance(v, str):
            return v
    return None


def build_tree(rows):
    titles = sorted({r["wiki"] for r in rows if r.get("wiki")})
    qid_for = {}
    for ch in chunks(titles, 50):
        j = api(WP, action="query", titles="|".join(ch), prop="pageprops", ppprop="wikibase_item", redirects=1)
        q = j.get("query", {})
        norm = {x["from"]: x["to"] for x in q.get("normalized", [])}
        red = {x["from"]: x["to"] for x in q.get("redirects", [])}
        pages = {p["title"]: p for p in q.get("pages", [])}
        for t in ch:
            f = norm.get(t, t)
            f = red.get(f, f)
            qi = pages.get(f, {}).get("pageprops", {}).get("wikibase_item")
            if qi:
                qid_for[t] = qi
        time.sleep(0.3)
    taxa, frontier = {}, set(qid_for.values())
    for _ in range(40):
        todo = sorted(q for q in frontier if q not in taxa)
        frontier = set()
        if not todo:
            break
        for ch in chunks(todo, 50):
            j = api(WD, action="wbgetentities", ids="|".join(ch), props="claims|labels", languages="en")
            for qid, e in j.get("entities", {}).items():
                if "missing" in e:
                    continue
                cl = e.get("claims", {})
                name = best_claim(cl, "P225") or e.get("labels", {}).get("en", {}).get("value") or qid
                rank = RANKS.get(best_claim(cl, "P105") or "", "")
                parent = None if name in STOP_AT else best_claim(cl, "P171")
                taxa[qid] = [name, rank, parent]
                if parent and parent not in taxa:
                    frontier.add(parent)
            time.sleep(0.3)
    dinos = {r["name"]: qid_for[r["wiki"]] for r in rows if r.get("wiki") in qid_for}
    # keep only taxa on some dinosaur's chain
    keep = set()
    for q in dinos.values():
        seen = set()
        while q and q in taxa and q not in seen:
            seen.add(q); keep.add(q); q = taxa[q][2]
    tree = {"taxa": {q: taxa[q] for q in sorted(keep)}, "dinos": dinos}
    (ROOT / "data/tree.json").write_text(json.dumps(tree, ensure_ascii=False, separators=(",", ":")))
    print(f"family tree: {len(dinos)} dinosaurs linked, {len(keep)} groups", file=sys.stderr)


if not OFFLINE:
    try:
        build_tree(rows)
    except Exception as e:  # the carousel works without the tree
        print("family tree failed:", repr(e), file=sys.stderr)

out = ROOT / "data/dinos.json"
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(rows, ensure_ascii=False, indent=0, separators=(",", ":")))
have = sum(1 for r in rows if r.get("img"))
print(f"{len(rows)} dinosaurs, {have} with pictures, {sum(1 for r in rows if r.get('wiki'))} with articles,"
      f" {sum(1 for r in rows if r.get('group'))} grouped, {sum(1 for r in rows if r.get('period'))} with period")
