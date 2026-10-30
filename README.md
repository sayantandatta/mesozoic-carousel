# Mesozoic Carousel

An endless carousel of about 750 dinosaurs, Aardonyx to Zupaysaurus. A random one swivels in from the right, says its name and what it ate, then the next one turns in. No dinosaur repeats until all of them have been shown.

Live site: https://sayantandatta.github.io/mesozoic-carousel/

## Apps

- **Install from the browser:** on Android (Chrome), Windows or Mac (Chrome or Edge) press **Install** under the title, or use the browser's *Install app* menu. On iPhone or iPad, tap Share, then *Add to Home Screen*. The installed app has its own icon, opens full screen, and works offline: dinosaurs you've seen keep their pictures, the rest are drawn.
- **Android APK:** [download mesozoic-carousel.apk](https://github.com/sayantandatta/mesozoic-carousel/releases/latest/download/mesozoic-carousel.apk) on an Android phone and open it. Android asks once to allow installs from your browser. It speaks with the phone's own text-to-speech and reads the latest dinosaur data from the website. The APK is built by `.github/workflows/android.yml` from the `app/` folder (Capacitor) on every change to the page, and each build is published as a GitHub release.
- The APK is signed with a shared debug key (`app/keystore/`) so new versions install over old ones. To publish on Google Play you'd need your own release key and a Play developer account.

- Press **Start** (browsers need a tap before a page can speak).
- **Pause**, **Next** and **Voice on/off** controls. Space pauses, → skips.
- Speech uses the browser's built-in voice (Web Speech API) in a neutral US English accent. The exact voice depends on the device; regional English voices are only used if the device has no US one.
- **Search** by name (press `/` to jump to the box). Picking a suggestion swivels straight to that dinosaur.
- **Filters** for diet, period, where it was found, length, hip type, family and pictures only, plus an **A to Z ribbon**. The endless loop then cycles only through the dinosaurs that match. Filters are kept in the address (for example `?place=asia&size=giant`), so a filtered view can be shared.
- **More like this** links on every card open the same period, continent, family, hip type or size, and a **Fossil photo** link appears where one is known.
- **Family tree** on every card opens a pop-up: the groups it belongs to run from Dinosauria at the top down to the dinosaur in the centre, with its closest relatives on the site underneath.
- **Every slide has its own address**, like `#Velociraptor`, so you can share or bookmark a dinosaur. In the family tree, each relative, the centre dinosaur and the members of every group (tap "N on this site") link to their slides, and the browser's back button returns to the previous one.

## Submitting images

Dinosaurs without a freely licensed picture show **No image available**. Anyone can offer one with **Submit an image** (in the top bar, on each no-image card and under About these pictures):

1. The picture goes on [Wikimedia Commons](https://commons.wikimedia.org/wiki/Special:UploadWizard) first, under CC0, public domain, CC BY or CC BY-SA. Commons checks open licences, so it is the standard used here. NC and ND licences are not accepted.
2. The form on the site checks the file on Commons, fills in the artist and licence, and opens a pre-filled [image submission issue](https://github.com/sayantandatta/mesozoic-carousel/issues/new?template=image-submission.yml) with the three licence agreement boxes.
3. The **Image submissions** workflow checks the file again and comments with a preview, the licence and the size.
4. To accept it, add the `image-approved` label. The workflow records it in `scripts/overrides.json`, removes any older clear-background pick, rebuilds the data and closes the issue. Only people with write access to the repository can add labels.

## Where the content comes from

- **Names:** the A to Z list at ThoughtCo, plus Brontosaurus and Stenonychosaurus, plus 26 more from DinoDatabase. Only the names are used. A few names that are now treated as the same animal (for example Seismosaurus and Diplodocus) appear once.
- **Facts:** each dinosaur's period, age and length are read from its English Wikipedia article. Its family comes from its Wikidata lineage (falling back to the article text), and "what it ate" is what that family is known to have eaten. The 51 best-known dinosaurs have hand-written facts and pronunciations in `index.html`.
- **Where found, hips, size, weight, species:** continents are read from each Wikipedia introduction; hip type follows the family; lengths and weights come from Wikipedia and from the size notes in [DinoDatabase](https://github.com/sopynya/DinoDatabase) by sopynya, which also supplies species names and fossil-photo links. DinoDatabase has no licence, so only plain facts are taken from it, not its text or images.
- **Family trees:** each dinosaur's chain of parent groups from Wikidata, saved in `data/tree.json`.
- **Pictures:** life restorations by paleoartists, hotlinked from Wikimedia Commons under free licences (CC BY, CC BY-SA, CC0 or public domain). Every picture links to its Commons page with the artist and licence. All automatically chosen pictures were reviewed by eye, and skeletons, museum models and size charts were swapped out. Where no suitable free picture exists, the page draws the dinosaur itself.

## Updating the data

`data/dinos.json` is built by `scripts/build_data.py`, which runs on GitHub Actions whenever anything in `scripts/` changes.

- `scripts/names.txt`: the dinosaur names.
- `scripts/overrides.json`: hand corrections. `{"pick": "<Commons file name>"}` swaps a picture, `{"img": null, ...}` uses the drawing, and any other field (`group`, `period`, `eats`, ...) replaces the value read from Wikipedia.
- `scripts/REUSE_IMAGES`: while this file exists, the build keeps the pictures it chose before and only refreshes the facts (a few minutes). Delete it to search Commons again (about 45 minutes).
- `python scripts/build_data.py --offline` re-runs the grouping from the cached Wikipedia text in `data/raw.json`, without touching the network.
