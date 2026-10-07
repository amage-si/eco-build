# eco-build

Fast builds of [AMAGE Eco](https://github.com/amage-si) programs (our UI
toolkit in Bend 2): one command per target, a few seconds per edit instead
of a minute and a half, and a memory peak near 1.2 GiB instead of 4–5 GiB.

```sh
./eco build demo            # dev build of Chromi/examples/eco/main.bend
./eco test chromi-tests     # build and run a suite
./eco build demo --release  # what `bend main.bend -o eco` produces
./eco targets               # the targets in targets.toml
```

`eco` lives beside the libraries (`amage-eco/build/`); targets name a
library directory, a source and an output, so `./eco build demo` writes
`Chromi/build/eco`, the path the Chromi README runs.

**Numbers:** see [Results](#results) (filled from `results/`).

## Where the time and the memory went

Bend 2.0.35 builds a native program in three steps, all inside one
`bend file.bend -o bin`:

| Step | AMAGE Eco demo | What it is |
|---|---|---|
| parse, imports, check | ~1.7 s, 0.7 GiB | `book_read`: fast |
| emit C | ~19 s, grows to 3+ GiB | `compile_book` in `comp.ts`: the whole program re-emitted until a fixpoint, 8 passes |
| clang | ~61 s, 1.5 GiB | one 7.9 MB C file, one unit, `-O3`, one core; while bend's 3 GiB heap stays resident |

Two facts drive the clang cost. The generated C is one translation unit,
so 8 cores sit idle. And every segment function (2,572 in the demo) has the
same signature, as wide as the widest value in the whole program: the
demo's 122-word UI model and Ankra's loop state made every segment take
206 parameters (`WL_SIG`) and every return save 122 words (`WL_RESW`).

## What eco does

1. **Emit C apart from clang.** `bend src -o out.c` exits before clang
   starts, so bend's heap is gone when clang runs. bend runs with
   `BUN_JSC_forceRAMSize` (default 2.4 GiB of "RAM" for JavaScriptCore's
   heap sizing): the same C, the peak drops from ~3 GiB to ~1.2 GiB, about
   2 s slower with the official binary.
2. **Split the C into units** (`ecobuild/csplit.py`). On the host every
   segment is already its own function, entered by `musttail`; unit 0
   gets the runtime (its globals defined once), the static image, the
   effects and `main`; the other units get the shared head (globals
   `extern`), the spins they reach (static inline) and a share of the
   segments, by a hash of their def's name. Segment functions get hidden
   external linkage. Programs with GPU calls are built as one unit.
3. **Compile the units in parallel with a cache.** Objects are cached in
   `~/.cache/eco-build/objs` by the unit's text, the flags and the clang
   version: an edit that leaves the def set alone recompiles only the
   units whose text changed. At most `--mem-budget` MiB (default 1536) of
   clang processes run at once, estimated from each unit's size.
4. **Link** (`-lpthread -lm`, plus X11/ALSA when the C includes them).

Dev builds use `-O1`; `--release` builds the unsplit C in one unit at
`-O3`, bend's own command line, so it matches `bend src -o out`.

### The compiler fork

When `../bend-fork/src` exists (a local fork of bendlang/bend v2.0.35, not
published), dev builds use it through `bun bend2/main.ts`; `--official`
forces the installed `bend`. In its default mode the fork emits the same C
as the official 2.0.35, byte for byte (checked on every runnable upstream
test and on the Eco programs; see `bend-fork/UPSTREAM.md`), three times
faster. Dev builds also set `BEND_FLAT_MAX=32`, which boxes datatypes wider
than 32 words: the C changes (every segment takes 61 parameters instead of
206) and clang's work halves; the Eco suites and the demo's reference
frames give the same output. `--flat-max 0` turns it off.

## Commands

```
eco build <target>... [--release] [--official|--fork] [-O N] [-j N]
                      [--units N] [--mem-budget MiB] [--heap-cap MiB]
                      [--flat-max N] [--root DIR] [--json FILE]
eco test <target>...   same options; runs the binary with the target's
                       `run` arguments and prints its last lines
eco targets
eco cache [--clean]
```

Every build takes the shared Eco build lock
(`/tmp/amage-eco-bend-build.lock`) and runs at `nice 10`; a wait for the
lock is printed apart from the build's own time.

`--root` builds a copy of the libraries (e.g. a snapshot) instead of the
working trees beside this repo.

## Results

Measured on Ian's laptop (Ryzen 7 5800H, 8 cores / 16 threads, 32 GB),
clang 22.1.8, bend 2.0.35 (Bun 1.4.0) and the fork on Bun 1.4.2; each
row's load average is in `results/`. Wall times include bend's startup.

(filled in by the measurement round)

## Layout

```
eco                 the command
ecobuild/cli.py     build driver: compiler, split, parallel cached clang, link
ecobuild/csplit.py  the C splitter
targets.toml        targets
tools/              measurement helpers: treemon (process-tree RSS), par,
                    cpuprof (Bun .cpuprofile summary), ctrace (clang
                    -ftime-trace summary), corpus (fork against bend)
results/            raw measurements (JSON), paths shown as <eco>
```

## License

MIT OR Apache-2.0.
