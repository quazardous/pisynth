"""The MIDI library on the Pi (#2421): one folder tree, `~/midi`, filled from three places. It holds MIDI
files and scores (MusicXML: `.musicxml`, `.xml`, compressed `.mxl`, #2657) — a score beside a MIDI file of
the same name is that song's sheet music; a score alone is a song of its own.

- `starter/…` — the Public Domain set shipped in the repo (library/midi), and
- anything in the repo's `midi/` folder — both LINKED in by sync.sh on every deploy;
- files uploaded from the web companion — REAL files, so a deploy never removes them.

The Pi only stores and serves bytes; the phone parses the files (thick phone, thin Pi). Every
path from the network is split into cleaned segments and must resolve inside the library or one
of the repo folders sync.sh links from — never anywhere else, whatever links or `..` it contains.
"""
import os

MAX_UPLOAD = 8 * 1024 * 1024                    # a MIDI file is small; a long score in plain MusicXML is not
MAX_READ = 16 * 1024 * 1024                     # a PC file too big to be a sane MIDI file or score isn't served
MIDI_EXT = (".mid", ".midi")
SCORE_EXT = (".musicxml", ".xml", ".mxl")
FOLDER_MARK = ".pisynth-folder"                 # a folder made from the phone: kept by deploys, deletable
MAX_SEGMENT = 120


class LibraryError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code, self.message = code, message


def clean_segment(seg):
    seg = seg.strip()
    if (not seg or seg in (".", "..") or seg.startswith(".") or len(seg) > MAX_SEGMENT
            or any(c in seg for c in "/\\\0") or any(ord(c) < 32 for c in seg)):
        raise LibraryError(400, f"bad name: {seg[:40]!r}")
    return seg


def split_path(path):
    """'a/b/c.mid' → ['a', 'b', 'c.mid'] with every segment cleaned; '' → []."""
    path = (path or "").strip().strip("/")
    return [clean_segment(s) for s in path.split("/")] if path else []


def is_midi_name(name):
    return name.lower().endswith(MIDI_EXT)


def is_score_name(name):
    return name.lower().endswith(SCORE_EXT)


def is_library_name(name):
    return is_midi_name(name) or is_score_name(name)


def file_kind(name):
    return "score" if is_score_name(name) else "midi"


def looks_like(name, data):
    """Does the content match the name? MIDI starts with MThd, .mxl is a zip, MusicXML is XML with a score."""
    if is_midi_name(name):
        return data[:4] == b"MThd"
    if name.lower().endswith(".mxl"):
        return data[:4] == b"PK\x03\x04"
    head = data[:4096].lstrip(b"\xef\xbb\xbf \t\r\n")
    return head.startswith(b"<") and (b"<score-partwise" in data[:65536] or b"<score-timewise" in data[:65536])


def content_type(name):
    n = name.lower()
    if n.endswith(".mxl"):
        return "application/vnd.recordare.musicxml"
    if n.endswith(SCORE_EXT):
        return "application/vnd.recordare.musicxml+xml"
    return "audio/midi"


class MidiLibrary:
    def __init__(self, root, sources=None, on_changed=None):
        """root: the library (~/midi). sources: {origin label: repo folder sync.sh links from}.
        on_changed(root): called after an upload/delete/new folder (read-only root write-through)."""
        self.root = os.path.abspath(root)
        self.sources = {k: os.path.realpath(v) for k, v in (sources or {}).items()}
        self.on_changed = on_changed

    # ---- paths ----
    def _inside(self, real):
        bases = [os.path.realpath(self.root), *self.sources.values()]
        return any(real == b or real.startswith(b + os.sep) for b in bases)

    def _path(self, parts):
        p = os.path.join(self.root, *parts)
        if not self._inside(os.path.realpath(p)):
            raise LibraryError(403, "outside the library")
        return p

    def origin(self, p):
        if os.path.islink(p):
            real = os.path.realpath(p)
            for label, base in self.sources.items():
                if real.startswith(base + os.sep):
                    return label
            return "link"
        return "phone"

    # ---- read ----
    def tree(self):
        """Every folder and MIDI file, depth-first: [{path, kind, size?, origin, deletable}]."""
        out = []
        if not os.path.isdir(self.root):
            return out

        def walk(rel):
            here = os.path.join(self.root, rel)
            try:
                names = sorted(os.listdir(here), key=str.lower)
            except OSError:
                return
            for name in names:
                if name.startswith("."):
                    continue
                p, r = os.path.join(here, name), f"{rel}/{name}" if rel else name
                if not self._inside(os.path.realpath(p)):
                    continue                          # a link pointing elsewhere is not listed
                if os.path.isdir(p) and not os.path.islink(p):
                    marked = os.path.exists(os.path.join(p, FOLDER_MARK))
                    out.append({"path": r, "kind": "dir", "origin": "phone" if marked else "sync",
                                "deletable": marked and self._only_mark(p)})
                    walk(r)
                elif is_library_name(name) and os.path.isfile(p):   # (a dangling link is not a file)
                    o = self.origin(p)
                    out.append({"path": r, "kind": "file", "type": file_kind(name), "size": os.path.getsize(p),
                                "origin": o, "deletable": o == "phone"})
        walk("")
        return out

    @staticmethod
    def _only_mark(p):
        try:
            return set(os.listdir(p)) <= {FOLDER_MARK}
        except OSError:
            return False

    def read(self, path):
        parts = split_path(path)
        if not parts or not is_library_name(parts[-1]):
            raise LibraryError(404, "not a MIDI file or a score")
        p = self._path(parts)
        if not os.path.isfile(p):
            raise LibraryError(404, "not found")
        if os.path.getsize(p) > MAX_READ:
            raise LibraryError(413, "file too large")
        with open(p, "rb") as f:
            return f.read()

    # ---- write ----
    def _ensure_dir(self, parts):
        cur = []
        for seg in parts:
            cur.append(seg)
            p = self._path(cur)
            if os.path.isdir(p):
                continue
            if os.path.lexists(p):
                raise LibraryError(409, f"{'/'.join(cur)} is a file")
            os.mkdir(p)
            open(os.path.join(p, FOLDER_MARK), "w").close()
        return self._path(parts)

    def save(self, folder, name, data):
        """Store an uploaded file in `folder` (created if needed). Returns its library path; a
        name already taken gets ' (2)', ' (3)'… before the extension."""
        if len(data) > MAX_UPLOAD:
            raise LibraryError(413, "file too large (8 MB max)")
        name = clean_segment(name or "")
        if not is_library_name(name):
            raise LibraryError(400, "the name must end in .mid, .midi, .musicxml, .xml or .mxl")
        if not looks_like(name, data):
            raise LibraryError(400, "not a MIDI file" if is_midi_name(name) else "not a MusicXML score")
        parts = split_path(folder)
        os.makedirs(self.root, exist_ok=True)
        d = self._ensure_dir(parts)
        stem, ext = os.path.splitext(name)
        final, k = name, 1
        while os.path.lexists(os.path.join(d, final)):
            k += 1
            if k > 99:
                raise LibraryError(409, "too many files with that name")
            final = f"{stem} ({k}){ext}"
        tmp = os.path.join(d, f".{final}.part")
        with open(tmp, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, os.path.join(d, final))
        self._changed()
        return "/".join([*parts, final])

    def mkdir(self, path):
        parts = split_path(path)
        if not parts:
            raise LibraryError(400, "folder name missing")
        if os.path.lexists(self._path(parts)):
            raise LibraryError(409, "already exists")
        os.makedirs(self.root, exist_ok=True)
        self._ensure_dir(parts)
        self._changed()
        return "/".join(parts)

    def delete(self, path):
        """Only what the phone added: an uploaded file, or an EMPTY folder made from the phone.
        PC and starter files come back on the next deploy, so they are refused."""
        parts = split_path(path)
        if not parts:
            raise LibraryError(403, "the library itself can't be deleted")
        p = os.path.join(self.root, *parts)
        if not os.path.lexists(p):
            raise LibraryError(404, "not found")
        if os.path.islink(p):
            raise LibraryError(403, "this file comes from the PC: delete it there and deploy")
        p = self._path(parts)
        if os.path.isdir(p):
            if not os.path.exists(os.path.join(p, FOLDER_MARK)):
                raise LibraryError(403, "this folder comes from the PC")
            if not self._only_mark(p):
                raise LibraryError(409, "the folder isn't empty")
            os.remove(os.path.join(p, FOLDER_MARK))
            os.rmdir(p)
        elif os.path.isfile(p) and is_library_name(parts[-1]):
            os.remove(p)
        else:
            raise LibraryError(404, "not found")
        self._changed()

    def _changed(self):
        if self.on_changed:
            try:
                self.on_changed(self.root)
            except Exception:                        # write-through is best effort, never fatal
                pass
