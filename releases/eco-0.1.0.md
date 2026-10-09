# AMAGE Eco 0.1.0 (2026-10-09)

The libraries import one another from source by relative path
(`import ../Syllo/main.bend`), so they work as a set: this file names the
versions that were built and tested together. Check each one out at its tag,
side by side in one directory, next to this repository.

| Library | Tag | Commit | Role |
|---|---|---|---|
| [Ankra](https://github.com/amage-si/ankra/tree/v0.1.0) | v0.1.0 | `eef92221edf2` | window, input, text input, clipboard |
| [Voltra](https://github.com/amage-si/voltra/tree/v0.1.0) | v0.1.0 | `bc5909651742` | Vulkan GPU, retained canvas, quad store |
| [Chromi](https://github.com/amage-si/chromi/tree/v0.1.0) | v0.1.0 | `42fc8f3d5afb` | draw lists, CPU/GPU rendering, retained frames, integrated demo |
| [Runika](https://github.com/amage-si/runika/tree/v0.1.0) | v0.1.0 | `603597c9de38` | TrueType reading |
| [Syllo](https://github.com/amage-si/syllo/tree/v0.1.0) | v0.1.0 | `c7298874764f` | text layout, caret queries |
| [Dithra](https://github.com/amage-si/dithra/tree/v0.1.0) | v0.1.0 | `e8db3d044d98` | glyph and path rasterization |
| [Tessra](https://github.com/amage-si/tessra/tree/v0.1.0) | v0.1.0 | `bd3a632966f1` | row/column layout, shared geometry |
| [Kairo](https://github.com/amage-si/kairo/tree/v0.1.0) | v0.1.0 | `6dec79c70883` | interaction, focus, editing |
| [Mokko](https://github.com/amage-si/mokko/tree/v0.1.0) | v0.1.0 | `2afbb2b0db69` | text, button and text-field components |
| [Ocula](https://github.com/amage-si/ocula/tree/v0.1.0) | v0.1.0 | `c9f44b1bad7d` | PNG decoding |
| [Splina](https://github.com/amage-si/splina/tree/v0.1.0) | v0.1.0 | `e3a5d394263f` | paths, transforms, SVG subset |
| [Auvia](https://github.com/amage-si/auvia/tree/v0.1.0) | v0.1.0 | `0d8d064db31a` | accessibility (AT-SPI2) |

Toolchain: Bend 2.0.35, Linux, X11/XWayland, Vulkan.

## Tested together

Every suite passed on these commits: Ankra 62, Voltra 79 + GPU, Chromi 73 +
27 GPU + 7 eco text, Runika 60, Syllo 26 + 45 caret, Dithra (whole text chain),
Tessra 20, Kairo 56 + 46 editing + 11 + 27 adapters, Mokko 14 + 5 + 26 field,
Ocula, Splina, Auvia 121. `./eco test` runs the registered ones.

The integrated demo (`./eco build demo`, Chromi `examples/eco`) was checked in
a real window: text with dead keys and AltGr, editing and selection, the
CLIPBOARD both ways, refusal of text the font cannot show, button activation,
the AT-SPI probe (27 checks) and Orca's announcements. Key to presented frame
about 0.8 ms; idle at 0 frames and 0 main-thread wakeups.

## Getting this set

```bash
for lib in ankra voltra chromi runika syllo dithra tessra kairo mokko ocula splina auvia; do
  git clone --branch v0.1.0 https://github.com/amage-si/$lib.git "${lib^}"
done
git clone https://github.com/amage-si/eco-build.git build
```

Each library's `CHANGELOG.md` lists what its 0.1.0 contains.
