# Mesozoic Carousel

An endless carousel of about 730 dinosaurs, Aardonyx to Zupaysaurus. A random one swivels in from the right, says its name and what it ate, then the next one turns in. No dinosaur repeats until all of them have been shown.

Live site: https://sayantandatta.github.io/mesozoic-carousel/

- Press **Start** (browsers need a tap before a page can speak).
- **Pause**, **Next** and **Voice on/off** controls. Space pauses, → skips.
- Speech uses the browser's built-in voice (Web Speech API), so the voice depends on the device.
- **Search** by name (press `/` to jump to the box). Picking a suggestion swivels straight to that dinosaur.
- **Filters** for diet, period, family and pictures only, plus an **A to Z ribbon**. The endless loop then cycles only through the dinosaurs that match.
- **Family tree** on every card opens a pop-up: the groups it belongs to run from Dinosauria at the top down to the dinosaur in the centre, with its closest relatives on the site underneath.

## Where the content comes from

- **Names:** the A to Z list at ThoughtCo, plus Brontosaurus and Stenonychosaurus. Only the names are used. A few names that are now treated as the same animal (for example Seismosaurus and Diplodocus) appear once.
- **Facts:** each dinosaur's period, age and length are read from its English Wikipedia article. Its family comes from the same text, and "what it ate" is what that family is known to have eaten. The 51 best-known dinosaurs have hand-written facts and pronunciations in `index.html`.
- **Family trees:** each dinosaur's chain of parent groups from Wikidata, saved in `data/tree.json`.
- **Pictures:** life restorations by paleoartists, hotlinked from Wikimedia Commons under free licences (CC BY, CC BY-SA, CC0 or public domain). Every picture links to its Commons page with the artist and licence. All automatically chosen pictures were reviewed by eye, and skeletons, museum models and size charts were swapped out. Where no suitable free picture exists, the page draws the dinosaur itself.

## Updating the data

`data/dinos.json` is built by `scripts/build_data.py`, which runs on GitHub Actions whenever anything in `scripts/` changes.

- `scripts/names.txt`: the dinosaur names.
- `scripts/overrides.json`: hand corrections. `{"pick": "<Commons file name>"}` swaps a picture, `{"img": null, ...}` uses the drawing, and any other field (`group`, `period`, `eats`, ...) replaces the value read from Wikipedia.
- `scripts/REUSE_IMAGES`: while this file exists, the build keeps the pictures it chose before and only refreshes the facts (a few minutes). Delete it to search Commons again (about 45 minutes).
- `python scripts/build_data.py --offline` re-runs the grouping from the cached Wikipedia text in `data/raw.json`, without touching the network.
