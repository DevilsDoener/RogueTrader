"""Extract the printed character/ship sheet pages from the Rogue Trader core
rulebook PDF and turn them into immutable, lossless background images.

This script renders pages 401-403 of the source PDF (the printed character
sheet, its second page, and the starship sheet) at a fixed, deterministic
resolution using ``pdftoppm``, converts each page to lossless WebP, strips
incidental metadata, and rotates the ship page (page 403) so that its header
reads horizontally with the output wider than it is tall.

The PDF itself is never committed to the repository; only these derived
images are. The script is intended to be run once (or re-run if the source
scan changes) by a human operator, not as part of the Django app or test
suite.

Usage::

    .venv\\Scripts\\python tools\\extract_sheet_assets.py \\
        --pdf "path\\to\\737639872-Rogue-Trader-Core-Rulebook.pdf" \\
        --pdftoppm "path\\to\\pdftoppm.exe" \\
        --output "sheets\\static\\sheets\\images"
"""
from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import NamedTuple

from PIL import Image

# The three source pages, in printed reading order, and the output filename
# stem each one is extracted to.
PAGE_PLAN: tuple[tuple[int, str], ...] = (
    (401, "character-page-1"),
    (402, "character-page-2"),
    (403, "ship-page"),
)

# The rulebook page count must be at least this large for pages 401-403 to
# exist. This is intentionally the exact page we need, not a margin -- if the
# supplied PDF is a different edition/printing with fewer pages, refuse to
# guess.
MINIMUM_PAGE_COUNT = 403

_PDFINFO_PAGES_RE = re.compile(r"^Pages:\s*(\d+)\s*$", re.MULTILINE)


class ExtractedPage(NamedTuple):
    stem: str
    path: Path
    sha256: str
    width: int
    height: int


def _pdfinfo_path(pdftoppm_path: Path) -> Path:
    """Return the expected path to ``pdfinfo`` alongside ``pdftoppm``."""
    suffix = pdftoppm_path.suffix
    name = "pdfinfo" + suffix
    return pdftoppm_path.with_name(name)


def _get_page_count(pdf_path: Path, pdftoppm_path: Path) -> int:
    pdfinfo_path = _pdfinfo_path(pdftoppm_path)
    if not pdfinfo_path.exists():
        raise FileNotFoundError(
            f"Expected pdfinfo alongside pdftoppm at {pdfinfo_path}, but it does not exist."
        )
    result = subprocess.run(
        [str(pdfinfo_path), str(pdf_path)],
        capture_output=True,
        text=True,
        check=True,
    )
    match = _PDFINFO_PAGES_RE.search(result.stdout)
    if not match:
        raise RuntimeError(
            f"Could not determine page count from pdfinfo output:\n{result.stdout}"
        )
    return int(match.group(1))


def _render_page(
    pdf_path: Path,
    pdftoppm_path: Path,
    page_number: int,
    dpi: int,
    tmp_dir: Path,
) -> Path:
    """Render a single PDF page to a lossless PNG using pdftoppm."""
    output_prefix = tmp_dir / f"page-{page_number}"
    cmd = [
        str(pdftoppm_path),
        "-r",
        str(dpi),
        "-f",
        str(page_number),
        "-l",
        str(page_number),
        "-png",
        "-singlefile",
        str(pdf_path),
        str(output_prefix),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    png_path = output_prefix.with_suffix(".png")
    if not png_path.exists():
        raise RuntimeError(f"pdftoppm did not produce the expected output at {png_path}")
    return png_path


def _strip_metadata(image: Image.Image) -> Image.Image:
    """Return a copy of ``image`` with no embedded metadata (EXIF/ICC/etc.)."""
    clean = Image.frombytes(image.mode, image.size, image.tobytes())
    return clean


def _sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract_assets(
    pdf_path: Path,
    pdftoppm_path: Path,
    output_dir: Path,
    dpi: int,
    rotate_ship_page: int,
) -> list[ExtractedPage]:
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    if not pdftoppm_path.exists():
        raise FileNotFoundError(f"pdftoppm executable not found: {pdftoppm_path}")

    page_count = _get_page_count(pdf_path, pdftoppm_path)
    if page_count < MINIMUM_PAGE_COUNT:
        raise ValueError(
            f"PDF has only {page_count} pages; expected at least "
            f"{MINIMUM_PAGE_COUNT} to contain the character/ship sheets."
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    results: list[ExtractedPage] = []

    with tempfile.TemporaryDirectory(prefix="sheet-extract-") as tmp:
        tmp_dir = Path(tmp)
        for page_number, stem in PAGE_PLAN:
            png_path = _render_page(pdf_path, pdftoppm_path, page_number, dpi, tmp_dir)
            with Image.open(png_path) as raw_image:
                image = raw_image.convert("RGB")

                if stem == "ship-page":
                    if rotate_ship_page:
                        # PIL's rotate() is counter-clockwise for positive
                        # angles; pass the negative so --rotate-403 90 means
                        # "rotate 90 degrees clockwise", matching how people
                        # describe turning a scanned page upright.
                        image = image.rotate(-rotate_ship_page, expand=True)
                    if image.width <= image.height:
                        raise ValueError(
                            "Ship page is not landscape after rotation "
                            f"(rotate={rotate_ship_page}): "
                            f"{image.width}x{image.height}. Pass a different "
                            "--rotate-403 value (0/90/180/270)."
                        )

                image = _strip_metadata(image)

                output_path = output_dir / f"{stem}.webp"
                image.save(
                    output_path,
                    format="WEBP",
                    lossless=True,
                    quality=100,
                    method=6,
                )

            sha256 = _sha256_of(output_path)
            results.append(
                ExtractedPage(
                    stem=stem,
                    path=output_path,
                    sha256=sha256,
                    width=image.width,
                    height=image.height,
                )
            )

    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", required=True, type=Path, help="Path to the source rulebook PDF.")
    parser.add_argument(
        "--pdftoppm",
        required=True,
        type=Path,
        help="Path to the pdftoppm executable (pdfinfo must be alongside it).",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Directory to write character-page-1.webp, character-page-2.webp, ship-page.webp into.",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=300,
        help="Rendering resolution in DPI (default: 300, a deterministic, "
        "print-quality resolution for this scan).",
    )
    parser.add_argument(
        "--rotate-403",
        type=int,
        choices=(0, 90, 180, 270),
        default=90,
        dest="rotate_403",
        help="Clockwise rotation in degrees applied to the ship page (page "
        "403) so its header reads horizontally and width exceeds height. "
        "Default 90; override if the source scan's binding orientation "
        "differs.",
    )
    args = parser.parse_args(argv)

    if shutil.which(str(args.pdftoppm)) is None and not args.pdftoppm.exists():
        parser.error(f"pdftoppm executable not found: {args.pdftoppm}")

    try:
        results = extract_assets(
            pdf_path=args.pdf,
            pdftoppm_path=args.pdftoppm,
            output_dir=args.output,
            dpi=args.dpi,
            rotate_ship_page=args.rotate_403,
        )
    except Exception as exc:  # noqa: BLE001 - surface any failure to the operator
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print("Extracted sheet assets:")
    for page in results:
        print(f"  {page.stem}.webp  {page.width}x{page.height}  sha256={page.sha256}")
        print(f"    -> {page.path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
