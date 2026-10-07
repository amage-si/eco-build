"""Split one C file emitted by `bend -o x.c` into translation units.

Bend 2.0.35 emits the whole program as one C file: the runtime, the
tables, the spins (inline loops), one function per segment, then the rest
of the runtime, the effects and main. clang compiles it as one unit on
one core. On the host every segment is already its own function, entered
by musttail through a table, so the segments can be compiled apart:

  unit 0   the runtime with its globals defined once, the static image,
           the effects and main (everything but the segments and spins)
  unit k   the shared head (globals as extern), the spins its segments
           reach, and a share of the segments

What changes against the single file:

  - the mutable globals of the head are defined in unit 0 and declared
    extern elsewhere (they hold the heap, the allocator and the pool);
  - the head's static prototypes defined later (in unit 0) and every
    segment function lose `static` and become hidden-visibility symbols;
  - static inline code (spins, runtime helpers) and read-only tables are
    repeated in each unit that uses them, as inline code in a header is.

Programs with GPU calls (`#define BANGS` not 0) embed their own source
for the device compiler; they are not split (split() returns None).

Segments are assigned to units by a hash of their def's name, so an edit
inside one def changes the unit holding it and leaves the others alone
while the def set is stable.
"""

import hashlib
import re

HEAD_END = "// Spins\n// =====\n"
WORK = "// Work\n// ====\n"
SEGS = "// Segments\n// ========\n"
TAIL = "// Monk\n// ====\n"
GLOBALS = "// Globals\n// =======\n"
TABLES = "// Tables\n// ======\n"

SEG_START = re.compile(r"^  WL_CASE\((\w+)\)$")
SPIN_DEF = re.compile(r"^(?:INLINE|FAR) Term (spin_\d+)\(", re.M)
SPIN_REF = re.compile(r"\b(spin_\d+)\(")
STATIC_PROTO = re.compile(r"^static ((?:\w+\s+)+\**)(\w+)\(([^()]*)\);$", re.M)

HIDDEN = '__attribute__((visibility("hidden")))'


class SplitError(Exception):
    pass


def _cut(text, marker, start=0):
    i = text.find(marker, start)
    if i < 0:
        raise SplitError("marker not found: " + marker.splitlines()[0])
    return i


def _globals(block):
    """Rewrite the Globals block twice: as extern declarations (for the
    segment units) and as definitions with external linkage (unit 0).
    Only mutable `static` objects change; `static const` stays."""
    decl, defn = [], []
    lines = block.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r"^static (?!const\b)(.+?);$", line)
        if m and "(" not in m.group(1).split("=")[0].split("__attribute__")[0]:
            body = m.group(1)
            name_part = body.split("=")[0].rstrip()
            decl.append("extern " + name_part + ";")
            defn.append(body + ";")
        else:
            decl.append(line)
            defn.append(line)
        i += 1
    return "\n".join(decl), "\n".join(defn)


def _segments(region):
    """Parse the segments region into (name, text) items and the device
    trailer. A segment may be wrapped in `#if !DEVICE` / `#endif`."""
    lines = region.split("\n")
    items, i, n = [], 0, len(lines)
    pre = []
    while i < n:
        line = lines[i]
        wrapped = line == "#if !DEVICE" and i + 1 < n and SEG_START.match(lines[i + 1])
        m = SEG_START.match(lines[i + 1] if wrapped else line)
        if not m:
            if items:
                break
            pre.append(line)
            i += 1
            continue
        j = i + 1 if wrapped else i
        k = j
        while k < n and lines[k] != "  }}":
            k += 1
        if k >= n:
            raise SplitError("unterminated segment " + m.group(1))
        end = k
        if wrapped:
            if k + 1 >= n or lines[k + 1] != "#endif":
                raise SplitError("unbalanced #if !DEVICE around " + m.group(1))
            end = k + 1
        items.append((m.group(1), "\n".join(lines[i:end + 1])))
        i = end + 1
        while i < n and lines[i] == "":
            i += 1
    trailer = "\n".join(lines[i:])
    if "WL_CASE(" in trailer:
        raise SplitError("segments after the device trailer")
    return "\n".join(pre), items, trailer


def _def_of(seg_name):
    """The def a segment belongs to: its name without the counter suffix
    the compiler appends to continuation and join segments."""
    return re.sub(r"_[A-Z]\d+$", "", seg_name)


def _unit_of(seg_name, units):
    h = hashlib.blake2b(_def_of(seg_name).encode(), digest_size=8).digest()
    return 1 + int.from_bytes(h, "little") % units


def split(c_text, units):
    """Return [unit0_text, unit1_text, ...] or None when the program
    cannot be split (GPU calls)."""
    m = re.search(r"^#define BANGS\s+(\d+)$", c_text, re.M)
    if m is None:
        raise SplitError("no BANGS define")
    if m.group(1) != "0":
        return None
    h_end = _cut(c_text, HEAD_END)
    w_at = _cut(c_text, WORK, h_end)
    s_at = _cut(c_text, SEGS, w_at)
    t_at = _cut(c_text, TAIL, s_at)
    head = c_text[:h_end]
    spins_region = c_text[h_end:w_at]
    work = c_text[w_at:s_at]
    segs_region = c_text[s_at:t_at]
    tail = c_text[t_at:]

    # globals: extern in segment units, defined once in unit 0
    g_at = _cut(head, GLOBALS)
    tb_at = _cut(head, TABLES, g_at)
    g_decl, g_defn = _globals(head[g_at:tb_at])
    head_ext = head[:g_at] + g_decl + head[tb_at:]
    head_def = head[:g_at] + g_defn + head[tb_at:]

    # static prototypes in the head whose bodies come later (unit 0)
    later = []
    for pm in STATIC_PROTO.finditer(head):
        name = pm.group(2)
        if re.search(r"^static (?:\w+\s+)+\**" + name + r"\([^;{]*\)\s*\{", head, re.M):
            continue
        later.append(name)
    for name in later:
        pat = re.compile(r"^static ((?:\w+\s+)+\**" + name + r"\()", re.M)
        head_ext = pat.sub(HIDDEN + r" \1", head_ext)
        head_def = pat.sub(HIDDEN + r" \1", head_def)
        tail, n = pat.subn(HIDDEN + r" \1", tail)
        if n != 1:
            raise SplitError("expected one definition of " + name + " after the segments")

    # segment functions get external (hidden) linkage everywhere
    fn_old = "#define WL_FN      static PRESERVE(preserve_none) __attribute__((noinline)) Term"
    if fn_old not in head:
        raise SplitError("WL_FN definition changed")
    fn_new = ("#define WL_FN      " + HIDDEN
              + " PRESERVE(preserve_none) __attribute__((noinline)) Term")
    head_ext = head_ext.replace(fn_old, fn_new)
    head_def = head_def.replace(fn_old, fn_new)

    # spins: the static image goes to unit 0; each spin to the units that reach it
    img = re.search(r"^CONSTV u64 STAT_IMG\[\] = .*;$", spins_region, re.M)
    if img is None:
        raise SplitError("no STAT_IMG")
    spin_text = spins_region[:img.start()] + spins_region[img.end():]
    starts = [sm.start() for sm in SPIN_DEF.finditer(spin_text)]
    spin_pre = spin_text[:starts[0]] if starts else spin_text
    spins = {}
    order = []
    for a, b in zip(starts, starts[1:] + [len(spin_text)]):
        body = spin_text[a:b]
        name = SPIN_DEF.match(body).group(1)
        spins[name] = body
        order.append(name)
    spin_deps = {k: set(SPIN_REF.findall(v)) - {k} for k, v in spins.items()}

    pre, items, trailer = _segments(segs_region)
    if not items:
        raise SplitError("no segments")

    groups = [[] for _ in range(units + 1)]
    for name, text in items:
        groups[_unit_of(name, units)].append(text)

    out = [head_def + spin_pre + img.group(0) + "\n\n" + work + pre + "\n"
           + trailer + "\n" + tail]
    for g in groups[1:]:
        body = "\n\n".join(g)
        need, todo = set(), set(SPIN_REF.findall(body)) & spins.keys()
        while todo:
            s = todo.pop()
            if s not in need:
                need.add(s)
                todo |= spin_deps[s] - need
        used = "".join(spins[s] for s in order if s in need)
        out.append(head_ext + spin_pre + used + work + pre + "\n" + body + "\n")
    return out


# Stable units
# ------------
#
# split() keeps the C's names and numbers, so an edit that adds a segment
# anywhere renames every later one (the compiler numbers segments across
# the whole program: def$k<count>), renumbers every FID and changes every
# unit. split_stable() makes the segment units depend only on their own
# segments' code:
#
#   - a suffixed segment's FID is renamed by its order inside its def
#     (FID_X_K4711 -> FID_X_k3), a spin by a hash of its text;
#   - FID numbers leave the units: each unit declares the FIDs it uses as
#     link-time constants (extern eco_FID_X, its address is the number,
#     given to the linker with --defsym; the program links without PIE so
#     the number lands in the instruction as an immediate);
#   - FID_T, wl_tab and STAT_IMG, which change with the numbering, live in
#     a small unit of their own ("tables"); unit 0 keeps the runtime.
#
# CIDs, static offsets and tables stay positional: an edit that adds a
# constructor or changes static data still rebuilds every unit.

SPIN_ANY = re.compile(r"\b(spin_\w+)\(")
FID_DEFINE = re.compile(r"^#define (FID_\w+) (\d+)\n", re.M)
FID_TOKEN = re.compile(r"\b(WL_)?(FID_[A-Za-z0-9_]+)\b")
SEG_SUFFIX = re.compile(r"^(FID_.+)_([CJK])(\d+)$")
FID_T_LINE = re.compile(r"^CONSTV u8 FID_T\[\]\[3\] = .*;\n", re.M)
WL_TABLE_LINE = re.compile(r"^#define WL_TABLE .*\n", re.M)
WORK_PROTOS = "WL_TABLE WL_X(FID_ENTER)\n"
WORK_TAB = "static const WlFn wl_tab[] = { WL_TABLE };\n"


def _canon_fids(c_text):
    names = [m.group(1) for m in FID_DEFINE.finditer(c_text)]
    groups = {}
    for name in names:
        m = SEG_SUFFIX.match(name)
        if m:
            groups.setdefault(m.group(1), []).append(
                (int(m.group(3)), m.group(2), name))
    ren = {}
    for prefix, xs in groups.items():
        for i, (_, letter, name) in enumerate(sorted(xs)):
            ren[name] = f"{prefix}_{letter.lower()}{i}"
    if len(set(ren.values())) != len(ren) or set(ren.values()) & set(names):
        raise SplitError("canonical FID names collide")

    def sub(m):
        new = ren.get(m.group(2))
        return m.group(0) if new is None else (m.group(1) or "") + new
    return FID_TOKEN.sub(sub, c_text)


SPIN_NAME = re.compile(r"\bspin_\d+\b")
LOCAL = re.compile(r"\b_([a-z][a-z0-9]*)_(\d+)\b")


def _canon_locals(body):
    """Renumber a function's locals (_v_26, _o_6...) by first appearance:
    a spin takes them from the def that emitted it first."""
    seen = {}

    def sub(m):
        key = m.group(0)
        if key not in seen:
            base = m.group(1)
            seen[key] = f"_{base}_{sum(1 for k in seen if k.startswith('_' + base + '_'))}"
        return seen[key]
    return LOCAL.sub(sub, body)


def _canon_spins(order, spins):
    """Rename spins by a hash of their text (locals renumbered), callees
    first (a spin only calls spins defined before it). Returns the new
    names and the new texts."""
    ren, seen, texts = {}, {}, {}
    for name in order:
        body = _canon_locals(spins[name])
        body = SPIN_NAME.sub(lambda m: "spin_SELF" if m.group(0) == name
                             else ren.get(m.group(0), m.group(0)), body)
        h = hashlib.blake2b(body.encode(), digest_size=8).hexdigest()
        n = seen.get(h, 0)
        seen[h] = n + 1
        ren[name] = f"spin_{h}" + (f"_{n}" if n else "")
        texts[ren[name]] = body.replace("spin_SELF", ren[name])
    return ren, texts


def _fid_decls(text):
    """Link-time FID constants and prototypes for the FIDs text uses."""
    used = sorted({m.group(2) for m in FID_TOKEN.finditer(text)} - {"FID_T"})
    out = []
    for f in used:
        out.append(f"extern const char eco_{f}[];\n"
                   f"#define {f} ((u32)(uintptr_t)eco_{f})\n")
    protos = "".join(f"WL_FN WL_{f}(WL_SIG);\n" for f in used)
    return "".join(out), protos, used


def split_stable(c_text, units):
    """Return (texts, fids) where texts is [unit0, tables, segment
    units...] and fids maps each FID to its number, or None for programs
    with GPU calls."""
    m = re.search(r"^#define BANGS\s+(\d+)$", c_text, re.M)
    if m is None:
        raise SplitError("no BANGS define")
    if m.group(1) != "0":
        return None
    text = _canon_fids(c_text)
    h_end = _cut(text, HEAD_END)
    w_at = _cut(text, WORK, h_end)
    s_at = _cut(text, SEGS, w_at)
    t_at = _cut(text, TAIL, s_at)
    head = text[:h_end]
    spins_region = text[h_end:w_at]
    work = text[w_at:s_at]
    segs_region = text[s_at:t_at]
    tail = text[t_at:]

    # spins: canonical names; the static image goes to the tables unit
    img = re.search(r"^CONSTV u64 STAT_IMG\[\] = .*;$", spins_region, re.M)
    if img is None:
        raise SplitError("no STAT_IMG")
    spin_text = spins_region[:img.start()] + spins_region[img.end():]
    starts = [sm.start() for sm in SPIN_DEF.finditer(spin_text)]
    spin_pre = spin_text[:starts[0]] if starts else spin_text
    spins, order = {}, []
    for a, b in zip(starts, starts[1:] + [len(spin_text)]):
        body = spin_text[a:b]
        name = SPIN_DEF.match(body).group(1)
        spins[name] = body
        order.append(name)
    sren, spins = _canon_spins(order, spins)
    order = [sren[k] for k in order]
    segs_region = SPIN_NAME.sub(lambda m: sren.get(m.group(0), m.group(0)),
                                segs_region)
    spin_deps = {k: set(SPIN_ANY.findall(v)) - {k} for k, v in spins.items()}

    # FID numbers out of the head; FID_T and WL_TABLE to the tables unit
    fids = {m.group(1): int(m.group(2)) for m in FID_DEFINE.finditer(head)}
    fid_t = FID_T_LINE.search(head)
    wl_table = WL_TABLE_LINE.search(head)
    if fid_t is None or wl_table is None:
        raise SplitError("no FID_T or WL_TABLE")
    head_tab = head.replace(fid_t.group(0), HIDDEN + " "
                            + fid_t.group(0).replace("CONSTV ", "const ", 1))
    head_bare = FID_DEFINE.sub("", head.replace(fid_t.group(0),
                               "extern const u8 FID_T[][3];\n")
                               .replace(wl_table.group(0), ""))

    def linkage(h, define):
        g_at = _cut(h, GLOBALS)
        tb_at = _cut(h, TABLES, g_at)
        g_decl, g_defn = _globals(h[g_at:tb_at])
        return h[:g_at] + (g_defn if define else g_decl) + h[tb_at:]

    head_def = linkage(head_bare, True)
    head_ext = linkage(head_bare, False)
    head_tab = linkage(head_tab, False)
    later = []
    for pm in STATIC_PROTO.finditer(head):
        name = pm.group(2)
        if not re.search(r"^static (?:\w+\s+)+\**" + name + r"\([^;{]*\)\s*\{", head, re.M):
            later.append(name)
    for name in later:
        pat = re.compile(r"^static ((?:\w+\s+)+\**" + name + r"\()", re.M)
        head_def = pat.sub(HIDDEN + r" \1", head_def)
        head_ext = pat.sub(HIDDEN + r" \1", head_ext)
        head_tab = pat.sub(HIDDEN + r" \1", head_tab)
        tail, n = pat.subn(HIDDEN + r" \1", tail)
        if n != 1:
            raise SplitError("expected one definition of " + name + " after the segments")
    fn_old = "#define WL_FN      static PRESERVE(preserve_none) __attribute__((noinline)) Term"
    fn_new = ("#define WL_FN      " + HIDDEN
              + " PRESERVE(preserve_none) __attribute__((noinline)) Term")
    if fn_old not in head:
        raise SplitError("WL_FN definition changed")
    head_def, head_ext, head_tab = (h.replace(fn_old, fn_new)
                                    for h in (head_def, head_ext, head_tab))

    # the work section: prototypes come from _fid_decls, wl_tab is extern;
    # the segment units leave work_loop out
    if WORK_PROTOS not in work or WORK_TAB not in work:
        raise SplitError("work section changed")
    work_ext = work.replace(WORK_PROTOS, "").replace(
        WORK_TAB, "extern const WlFn wl_tab[];\n")
    loop_at = work_ext.find("static Term work_loop(")
    if loop_at < 0:
        raise SplitError("no work_loop")
    work_seg = work_ext[:loop_at]

    pre, items, trailer = _segments(segs_region)
    if not items:
        raise SplitError("no segments")
    groups = [[] for _ in range(units + 1)]
    for name, seg in items:
        groups[_unit_of(name, units)].append(seg)

    def with_fids(h, rest, protos_at):
        decls, protos, _ = _fid_decls(h + rest)
        return h + decls + rest.replace(protos_at, protos_at + protos, 1)

    typedef = "typedef Term (PRESERVE(preserve_none) *WlFn)(WL_SIG);\n"
    if typedef not in work:
        raise SplitError("no WlFn typedef")
    unit0 = with_fids(head_def, spin_pre + "extern const u64 STAT_IMG[];\n\n"
                      + work_ext + pre + "\n" + trailer + "\n" + tail, typedef)
    tables = (head_tab + "\n#if !DEVICE\n" + typedef
              + "#define WL_X(F) WL_FN WL_##F(WL_SIG);\nWL_TABLE WL_X(FID_ENTER)\n"
              + "#undef WL_X\n#define WL_X(F) WL_##F,\n" + HIDDEN
              + " const WlFn wl_tab[] = { WL_TABLE };\n#undef WL_X\n#endif\n"
              + HIDDEN + " " + img.group(0).replace("CONSTV ", "const ", 1) + "\n")
    out = [unit0, tables]
    for g in groups[1:]:
        body = "\n\n".join(g)
        need, todo = set(), set(SPIN_ANY.findall(body)) & spins.keys()
        while todo:
            s = todo.pop()
            if s not in need:
                need.add(s)
                todo |= spin_deps[s] - need
        used = "".join(spins[s] for s in order if s in need)
        out.append(with_fids(head_ext, spin_pre + used + work_seg + pre + "\n"
                             + body + "\n", typedef))
    return out, fids
