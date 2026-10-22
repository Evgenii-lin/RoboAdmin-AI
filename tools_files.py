"""File tools shared by all agents.

Uploads "not found" fixes:
  * paths are anchored to APP_DIR (see paths.py), not the process CWD,
  * list_uploads lets the model discover what files actually exist,
  * a failed read tells the model the available filenames, so it can retry.

Also: save_config_file (agent-generated configs land in ./configs),
and read_document (used by the GUI on Upload).
"""
from __future__ import annotations

from pathlib import Path

from smolagents import tool

from paths import APP_DIR, CONFIGS_DIR, DOCKER_DIR, UPLOADS_DIR


def _resolve_upload(file_path: str) -> Path | None:
    """Resolve a model-supplied path to an existing file, or None."""
    p = Path(file_path).expanduser()
    if p.is_absolute():
        return p if p.is_file() else None
    # try relative to the app dir, then uploads/, then docker_containers/, then configs/
    for base in (APP_DIR, UPLOADS_DIR, DOCKER_DIR, CONFIGS_DIR):
        cand = base / p
        if cand.is_file():
            return cand
    # last resort: bare filename living somewhere in uploads/
    cand = UPLOADS_DIR / p.name
    return cand if cand.is_file() else None


def _available() -> str:
    if not UPLOADS_DIR.is_dir():
        return "(none)"
    files = sorted(x.name for x in UPLOADS_DIR.iterdir() if x.is_file())
    return ", ".join(files) if files else "(none)"


@tool
def list_uploads() -> str:
    """List the files the user has uploaded, one filename per line.

    Call this FIRST to discover which files exist before reading them.
    """
    UPLOADS_DIR.mkdir(exist_ok=True)
    files = sorted(x.name for x in UPLOADS_DIR.iterdir() if x.is_file())
    if not files:
        return "The uploads directory is empty. Ask the user to upload files first."
    return "\n".join(files)


@tool
def file_reader(file_path: str) -> str:
    """Read the text content of a file uploaded by the user (or a file in
    ./docker_containers or ./configs).

    Pass just the filename (e.g. "nginx.conf") or a path like "uploads/nginx.conf".
    If unsure which files exist, call list_uploads first.

    Args:
        file_path: Filename or path of the file to read.
    """
    p = _resolve_upload(file_path)
    if p is None:
        return (
            f"ERROR: file not found: '{file_path}'. "
            f"Available files: {_available()}."
        )
    # utf-8 first, latin-1 as fallback for legacy .cfg / .conf files
    for enc in ("utf-8", "latin-1"):
        try:
            return p.read_text(encoding=enc)
        except (UnicodeDecodeError, UnicodeError):
            continue
    return f"ERROR: could not decode '{p}' as text (binary file?)"


@tool
def save_config_file(filename: str, content: str) -> str:
    """Save a generated configuration file (Linux service config, network .cfg,
    SQL script, …) into the app's ./configs directory and return its full path.

    Use this after creating a configuration so it exists on disk instead of
    only in the chat. Network .cfg files saved here are audited by Batfish.

    Args:
        filename: File name only, e.g. "nginx.conf", "rtr-core-01.cfg" or "schema.sql"
        content: The full file content to save.
    """
    name = Path(filename).name  # strip any path the model might have added
    if not name or name.startswith("."):
        return f"ERROR: invalid filename '{filename}'. Use e.g. 'nginx.conf'."
    CONFIGS_DIR.mkdir(parents=True, exist_ok=True)
    dest = CONFIGS_DIR / name
    dest.write_text(content, encoding="utf-8")
    return f"Saved {dest} ({len(content)} chars). Path: {dest}"


# ──────────────────────────────────────────────
# Document reading (used by the GUI on Upload)
# ──────────────────────────────────────────────

def _extract_pdf_text(path: Path) -> str:
    """Extract text from a PDF, page by page, using pypdf."""
    try:
        from pypdf import PdfReader
    except ImportError as e:
        raise ValueError(
            "pypdf is not installed, so PDF files cannot be opened.\n"
            "Install it with:  pip install pypdf"
        ) from e

    reader = PdfReader(str(path))
    if reader.is_encrypted and not reader.decrypt(""):
        raise ValueError("This PDF is password-protected. Remove the password and try again.")

    pages = []
    for i, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            pages.append(f"[Page {i}]\n{text}" if len(reader.pages) > 1 else text)

    content = "\n\n".join(pages).strip()
    if not content:
        raise ValueError("No extractable text found in this PDF.")
    return content


def read_document(file_path: str) -> str:
    """Return the text content of a .txt/.conf or a .pdf file.

    Raises a ValueError with a user-friendly message on failure.
    """
    path = Path(file_path)
    if path.suffix.lower() == ".pdf":
        return _extract_pdf_text(path)

    for enc in ("utf-8", "latin-1"):
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")
