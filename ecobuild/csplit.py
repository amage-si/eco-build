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
