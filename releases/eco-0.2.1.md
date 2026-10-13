# AMAGE Eco 0.2.1 (2026-10-13)

The same library versions as [0.2.0](eco-0.2.0.md), now built and tested on the
official **Bend 2.0.37**. No library changed. eco's C splitter learned the
`DFAR` spin qualifier that 2.0.37 emits (upstream #1413); without it, split
builds failed with a KeyError.

| Library | Tag | Commit |
|---|---|---|
| [Ankra](https://github.com/amage-si/ankra/tree/v0.2.0) | v0.2.0 | `f0c7e7fc4047` |
| [Voltra](https://github.com/amage-si/voltra/tree/v0.1.2) | v0.1.2 | `8900b07e14b8` |
| [Chromi](https://github.com/amage-si/chromi/tree/v0.2.0) | v0.2.0 | `70555a40a809` |
| [Runika](https://github.com/amage-si/runika/tree/v0.1.0) | v0.1.0 | `603597c9de38` |
| [Syllo](https://github.com/amage-si/syllo/tree/v0.1.0) | v0.1.0 | `c7298874764f` |
| [Dithra](https://github.com/amage-si/dithra/tree/v0.1.0) | v0.1.0 | `e8db3d044d98` |
| [Tessra](https://github.com/amage-si/tessra/tree/v0.1.0) | v0.1.0 | `bd3a632966f1` |
| [Kairo](https://github.com/amage-si/kairo/tree/v0.1.0) | v0.1.0 | `6dec79c70883` |
| [Mokko](https://github.com/amage-si/mokko/tree/v0.2.0) | v0.2.0 | `705e9987ed01` |
| [Ocula](https://github.com/amage-si/ocula/tree/v0.1.0) | v0.1.0 | `c9f44b1bad7d` |
| [Splina](https://github.com/amage-si/splina/tree/v0.1.0) | v0.1.0 | `e3a5d394263f` |
| [Auvia](https://github.com/amage-si/auvia/tree/v0.1.1) | v0.1.1 | `ba48b71d8f25` |
| [Kinera](https://github.com/amage-si/kinera/tree/v0.1.0) (new) | v0.1.0 | `8d695e8724be` |

Toolchain: Bend 2.0.37 (official), Linux, X11/XWayland, Vulkan.

## Tested on 2.0.37

- **Test suites:** all 23 `./eco test` targets pass with the same counts as
  0.2.0.
- **Builds:** the demo, the grid, the reference and voltra-motion build.
- **Reference frames:** the 900x560 and 640x760 frames are byte-identical.
