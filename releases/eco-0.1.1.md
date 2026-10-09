# AMAGE Eco 0.1.1 (2026-10-09)

AMAGE Eco moves to the official **Bend 2.0.36**. The only break for us was
in how native effects are registered (upstream bendlang/bend#1281: `io_eff`
lost its third argument; an effect that waits parks itself), so the three
libraries with a native bridge get a patch release. The public APIs are
unchanged. The other nine keep their 0.1.0 tags, which build and pass
unchanged on 2.0.36.

| Library | Tag | Commit |
|---|---|---|
| [Ankra](https://github.com/amage-si/ankra/tree/v0.1.1) | v0.1.1 | `f410ab17b4a4` |
| [Voltra](https://github.com/amage-si/voltra/tree/v0.1.1) | v0.1.1 | `554f456b98af` |
| [Chromi](https://github.com/amage-si/chromi/tree/v0.1.0) | v0.1.0 | `42fc8f3d5afb` |
| [Runika](https://github.com/amage-si/runika/tree/v0.1.0) | v0.1.0 | `603597c9de38` |
| [Syllo](https://github.com/amage-si/syllo/tree/v0.1.0) | v0.1.0 | `c7298874764f` |
| [Dithra](https://github.com/amage-si/dithra/tree/v0.1.0) | v0.1.0 | `e8db3d044d98` |
| [Tessra](https://github.com/amage-si/tessra/tree/v0.1.0) | v0.1.0 | `bd3a632966f1` |
| [Kairo](https://github.com/amage-si/kairo/tree/v0.1.0) | v0.1.0 | `6dec79c70883` |
| [Mokko](https://github.com/amage-si/mokko/tree/v0.1.0) | v0.1.0 | `2afbb2b0db69` |
| [Ocula](https://github.com/amage-si/ocula/tree/v0.1.0) | v0.1.0 | `c9f44b1bad7d` |
| [Splina](https://github.com/amage-si/splina/tree/v0.1.0) | v0.1.0 | `e3a5d394263f` |
| [Auvia](https://github.com/amage-si/auvia/tree/v0.1.1) | v0.1.1 | `ba48b71d8f25` |

Toolchain: Bend 2.0.36 (official; `eco` builds with the installed bend by
default), Linux, X11/XWayland, Vulkan.

## Tested together on 2.0.36

- **Test suites:** all 21 `./eco test` targets pass with the same counts as
  0.1.0.
- **Builds:** the demo, the grid and the reference build.
- **Reference frames:** the frames at 900x560 and 640x760 are byte-identical
  to 0.1.0's.
- **Demo window:** driven with events sent to the window only. Tab, Space,
  typing into the field, resize and close work, with 0 native objects left.
  The AT-SPI probe passes 30/30, and idle stays at 0 frames.
- **Speed:** build time and runtime are on par with 2.0.35.

See [eco-0.1.0.md](eco-0.1.0.md) for what the libraries contain, and each
library's CHANGELOG.md for 0.1.1.
