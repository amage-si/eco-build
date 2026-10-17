# AMAGE Eco 0.2.2 (2026-10-17)

This release gets ready for the next Bend release. Upstream main adds a
`Text` constructor to Base's `Event` (bendlang/bend#1441), and Auvia's own
`Text` record would then stop every program that imports Auvia with
"duplicate declaration of Text":

- **Auvia 0.2.0** renames its text record to `NodeText`. This is a breaking
  rename only; behaviour is unchanged.
- **Chromi 0.2.1** renames the eco text tests' local sample record.

The other libraries are unchanged.

| Library | Tag | Commit |
|---|---|---|
| [Ankra](https://github.com/amage-si/ankra/tree/v0.2.0) | v0.2.0 | `f0c7e7fc4047` |
| [Voltra](https://github.com/amage-si/voltra/tree/v0.1.2) | v0.1.2 | `8900b07e14b8` |
| [Chromi](https://github.com/amage-si/chromi/tree/v0.2.1) | v0.2.1 | `3ecf824d37cc` |
| [Runika](https://github.com/amage-si/runika/tree/v0.1.0) | v0.1.0 | `603597c9de38` |
| [Syllo](https://github.com/amage-si/syllo/tree/v0.1.0) | v0.1.0 | `c7298874764f` |
| [Dithra](https://github.com/amage-si/dithra/tree/v0.1.0) | v0.1.0 | `e8db3d044d98` |
| [Tessra](https://github.com/amage-si/tessra/tree/v0.1.0) | v0.1.0 | `bd3a632966f1` |
| [Kairo](https://github.com/amage-si/kairo/tree/v0.1.0) | v0.1.0 | `6dec79c70883` |
| [Mokko](https://github.com/amage-si/mokko/tree/v0.2.0) | v0.2.0 | `705e9987ed01` |
| [Ocula](https://github.com/amage-si/ocula/tree/v0.1.0) | v0.1.0 | `c9f44b1bad7d` |
| [Splina](https://github.com/amage-si/splina/tree/v0.1.0) | v0.1.0 | `e3a5d394263f` |
| [Auvia](https://github.com/amage-si/auvia/tree/v0.2.0) | v0.2.0 | `a89e9a15f230` |
| [Kinera](https://github.com/amage-si/kinera/tree/v0.1.0) | v0.1.0 | `8d695e8724be` |

Toolchain: Bend 2.0.37 (official), Linux, X11/XWayland, Vulkan.

## Tested

- **Bend 2.0.37:**
  - auvia-tests: 121 checks;
  - chromi-text-tests: 7 checks;
  - the demo and the grid build;
  - Auvia's headless, counter and bus_probe examples build.
- **Upstream Bend main (e5527d5b), not yet released:** the eco demo, Auvia's
  tests, the eco text tests and Auvia's headless example emit C. Before the
  rename they failed with the duplicate declaration.
