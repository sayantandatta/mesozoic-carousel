# Mesozoic Carousel

An endless carousel of 51 dinosaurs. A random one swivels in from the right, says its name and what it ate, then the next one turns in. No dinosaur repeats until all 51 have been shown.

Live site: https://sayantandatta.github.io/mesozoic-carousel/

- Press **Start** (browsers need a tap before a page can speak).
- **Pause**, **Next** and **Voice on/off** controls. Space pauses, → skips.
- Pictures are life restorations by paleoartists, hotlinked from Wikimedia Commons under their free licences (CC BY, CC BY-SA, CC0 or public domain). Each picture links to its Commons page with the artist and licence. If a picture can't load, the page draws that dinosaur instead. Abelisaurus and Minmi have no suitable free restoration yet, so they always use the drawing.
- Speech uses the browser's built-in voice (Web Speech API), so the voice depends on the device.

One static file, `index.html`. No build step.
