"""
Verify every SHA256 the repository records against the tracked files.

Many hashes in this repository were taken on Windows, where Git checks text
files out with CRLF line endings. On a Linux or macOS checkout (LF) those
hashes do not match the bytes on disk, although the content is the same. This
script makes the records checkable on any platform. For each recorded hash it
reports whether the file it names matches

  as-is     the bytes on disk,
  CRLF      the file with LF converted to CRLF (a Windows checkout),
  LF        the file with CRLF converted to LF,

or, when the record names no tracked file,

  found     the hash nonetheless matches some tracked file (reported),
  external  it refers to an untracked artefact (bitstream, XSA, archived
            simulation output) - listed, not failed.

Members of tracked .zip archives count as files: results/round3.zip holds
results/round3/best_model.pt.

Sources of records:
  * PowerShell Get-FileHash output (*_sha256.txt, UTF-16),
  * SHA256SUMS files (sha256sum format),
  * the standalone RTL manifests (hls/reports/*/manifest.json),
  * any Markdown line holding a 64-hex-digit hash; the file is the first
    `backticked` name on that line that resolves to a tracked file.

Exit status 1 if a record names a tracked file and matches it in no form.

Usage: python tools/verify_recorded_hashes.py [--verbose]
"""

from pathlib import Path, PurePosixPath, PureWindowsPath
import hashlib
import json
import posixpath
import re
import subprocess
import sys
import zipfile


ROOT = Path(__file__).resolve().parent.parent
REPO_NAME = "meng-fpga-neural-reconstruction"
HEX = re.compile(r"\b[0-9a-fA-F]{64}\b")
TICKED = re.compile(r"`([^`]+)`")

RTL_ORIGIN = "vivado/ip_repo/reconstruction_accel_1_0/hdl/verilog"


def digests(data):
    """sha256 of the bytes as-is, in CRLF form and in LF form."""
    forms = {"as-is": data}
    if b"\0" not in data:
        lf = data.replace(b"\r\n", b"\n")
        forms["LF"] = lf
        forms["CRLF"] = lf.replace(b"\n", b"\r\n")
    return {form: hashlib.sha256(b).hexdigest() for form, b in forms.items()}


class Index:
    """Tracked files plus the members of tracked zip archives."""

    def __init__(self):
        out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT,
                             capture_output=True, check=True).stdout
        self.files = [p for p in out.decode().split("\0") if p]

        self.readers = {path: (lambda p=path: (ROOT / p).read_bytes())
                        for path in self.files}
        for path in self.files:
            if path.endswith(".zip"):
                parent = str(PurePosixPath(path).parent)
                with zipfile.ZipFile(ROOT / path) as archive:
                    for member in archive.namelist():
                        if member.endswith("/"):
                            continue
                        virtual = posixpath.normpath(f"{parent}/{member}")
                        self.readers.setdefault(
                            virtual,
                            lambda z=path, m=member:
                                zipfile.ZipFile(ROOT / z).read(m))

        self.by_name = {}
        for path in self.readers:
            self.by_name.setdefault(PurePosixPath(path).name, []).append(path)

        self._digests = {}
        self._reverse = None

    def digests(self, path):
        if path not in self._digests:
            self._digests[path] = digests(self.readers[path]())
        return self._digests[path]

    def resolve(self, name, base_dir):
        """Map a recorded name to one tracked path, or None.

        Tries the name relative to the recording file's directory, then to
        the repository root, then a unique basename match.
        """
        name = name.strip().replace("\\", "/")
        candidates = [name]
        if base_dir:
            candidates.insert(0, f"{base_dir}/{name}")
        for candidate in candidates:
            candidate = posixpath.normpath(candidate)
            if candidate in self.readers:
                return candidate
        matches = self.by_name.get(PurePosixPath(name).name, [])
        return matches[0] if len(matches) == 1 else None

    def lookup(self, digest):
        """Find any tracked file whose content has this hash."""
        if self._reverse is None:
            self._reverse = {}
            for path in self.readers:
                for form, value in self.digests(path).items():
                    self._reverse.setdefault(value, (path, form))
        return self._reverse.get(digest)


# ---------------------------------------------------------------------------
# Record collection: (source file, [candidate names], base dir, sha256)
# ---------------------------------------------------------------------------

def powershell_records(path):
    lines = (ROOT / path).read_bytes().decode("utf-16").splitlines()
    digest = None
    for i, line in enumerate(lines):
        if line.startswith("Hash"):
            digest = line.split(":", 1)[1].strip().lower()
        elif line.startswith("Path") and digest:
            recorded = line.split(":", 1)[1].strip()
            for more in lines[i + 1:]:             # wrapped continuation
                if not more.startswith(" ") or not more.strip():
                    break
                recorded += more.strip()
            parts = PureWindowsPath(recorded).parts
            if REPO_NAME in parts:
                relative = "/".join(parts[parts.index(REPO_NAME) + 1:])
            else:
                relative = parts[-1]
            yield path, [relative], "", digest
            digest = None


def sha256sums_records(path):
    base_dir = str(PurePosixPath(path).parent)
    for line in (ROOT / path).read_text().splitlines():
        match = re.match(r"([0-9a-fA-F]{64}) [ *](.+)", line)
        if match:
            yield path, [match.group(2)], base_dir, match.group(1).lower()


def manifest_records(path):
    manifest = json.loads((ROOT / path).read_text())
    for name, entry in manifest.get("files", {}).items():
        yield path, [f"{RTL_ORIGIN}/{name}"], "", entry["sha256"].lower()
    for name, digest in manifest.get("sources", {}).items():
        yield path, [f"hls/src/{name}"], "", digest.lower()
    for frame, entry in manifest.get("golden_files", {}).items():
        yield (path, [f"hls/tb/data/{frame}/input_lr_u8.bin"], "",
               entry["input_sha256"].lower())
        yield (path, [f"hls/tb/data/{frame}/output_ticks_u16.bin"], "",
               entry["output_sha256"].lower())


def markdown_records(path):
    base_dir = str(PurePosixPath(path).parent)
    for line in (ROOT / path).read_text(encoding="utf-8").splitlines():
        found = HEX.findall(line)
        names = [t for t in TICKED.findall(line) if not HEX.fullmatch(t)]
        for digest in found:
            yield path, names, base_dir, digest.lower()


def collect(index):
    for path in index.files:
        name = PurePosixPath(path).name
        if name.endswith("_sha256.txt"):
            yield from powershell_records(path)
        elif name == "SHA256SUMS":
            yield from sha256sums_records(path)
        elif name == "manifest.json" and path.startswith("hls/reports/"):
            yield from manifest_records(path)
        elif name.endswith(".md"):
            yield from markdown_records(path)


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

ORDER = ["as-is", "CRLF", "LF", "found", "external", "MISMATCH"]


def verify(index, names, base_dir, digest):
    """Return (verdict, label)."""
    for name in names:
        target = index.resolve(name, base_dir)
        if target is None:
            continue
        forms = [f for f, v in index.digests(target).items() if v == digest]
        if not forms:
            return "MISMATCH", target
        return ("as-is" if "as-is" in forms else forms[0]), target

    hit = index.lookup(digest)
    if hit:
        return "found", f"{hit[0]} ({hit[1]})"
    return "external", names[0] if names else "(unnamed)"


def main():
    verbose = "--verbose" in sys.argv
    index = Index()

    results = []
    for source, names, base_dir, digest in collect(index):
        verdict, label = verify(index, names, base_dir, digest)
        results.append((source, label, verdict))

    by_source = {}
    for source, _, verdict in results:
        counts = by_source.setdefault(source, {})
        counts[verdict] = counts.get(verdict, 0) + 1

    width = max(len(s) for s in by_source) + 2
    print(f"{'record file':{width}}" + "".join(f"{v:>9}" for v in ORDER))
    for source in sorted(by_source):
        print(f"{source:{width}}"
              + "".join(f"{by_source[source].get(v, 0):>9}" for v in ORDER))

    if verbose:
        print()
        for source, label, verdict in results:
            print(f"{verdict:9} {label}   [{source}]")

    totals = {v: sum(1 for *_, x in results if x == v) for v in ORDER}
    print()
    print(f"{len(results)} records: "
          + ", ".join(f"{totals[v]} {v}" for v in ORDER))

    mismatches = [(s, label) for s, label, v in results if v == "MISMATCH"]
    for source, label in mismatches:
        print(f"MISMATCH: {label} (recorded in {source})")

    if mismatches:
        print("RECORDED HASHES: FAIL")
        return 1
    print("RECORDED HASHES: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
