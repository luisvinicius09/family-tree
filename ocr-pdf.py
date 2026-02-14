import argparse
import re
import shutil
import sys
from pathlib import Path

from docling.document_converter import DocumentConverter
from docling.datamodel.settings import PageRange


def _markdown_to_text(markdown: str) -> str:
    text = re.sub(r"```.*?```", "", markdown, flags=re.S)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"^#+\s*", "", text, flags=re.M)
    text = re.sub(r"[*_]{1,2}", "", text)
    text = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1", text)
    return text.strip()


def _build_converter(lang: str, enable_ocr: bool) -> DocumentConverter:
    pipeline_options = None
    if enable_ocr:
        try:
            from docling.datamodel.pipeline_options import PdfPipelineOptions
            from docling.datamodel.ocr_options import OcrOptions

            pipeline_options = PdfPipelineOptions()
            if hasattr(pipeline_options, "ocr_options"):
                pipeline_options.ocr_options = OcrOptions(lang=[lang])
        except Exception:
            pipeline_options = None

    if pipeline_options is not None:
        try:
            return DocumentConverter(pipeline_options=pipeline_options)
        except TypeError:
            return DocumentConverter()
    return DocumentConverter()


def _write_pdf(exported_pdf, output_path: Path) -> bool:
    if exported_pdf is None:
        return False
    if isinstance(exported_pdf, (bytes, bytearray)):
        output_path.write_bytes(exported_pdf)
        return True
    if isinstance(exported_pdf, str):
        shutil.copy(exported_pdf, output_path)
        return True
    if hasattr(exported_pdf, "read"):
        output_path.write_bytes(exported_pdf.read())
        return True
    return False


def _parse_page_range(pages: str) -> PageRange:
    if pages.strip().lower() in {"all", "*"}:
        return (1, sys.maxsize)
    if "-" in pages:
        start_str, end_str = pages.split("-", 1)
        start = int(start_str.strip()) if start_str.strip() else 1
        end = int(end_str.strip()) if end_str.strip() else None
    else:
        start = int(pages.strip())
        end = start
    if start < 1:
        raise ValueError("Page ranges are 1-based (start >= 1)")
    if end is not None and end < start:
        raise ValueError("Page range end must be >= start")
    if end is None:
        return (start, sys.maxsize)
    return (start, end)


def main() -> int:
    parser = argparse.ArgumentParser(description="OCR a PDF with Docling")
    parser.add_argument(
        "--input",
        default="family-history-book.pdf",
        help="Path to input PDF",
    )
    parser.add_argument(
        "--out-dir",
        default="output",
        help="Output directory for OCR artifacts",
    )
    parser.add_argument(
        "--lang",
        default="pt",
        help="OCR language (e.g., pt)",
    )
    parser.add_argument(
        "--pages",
        default="1-10",
        help="Page range (1-based, e.g., 1-10 or 5- or all)",
    )
    parser.add_argument(
        "--ocr",
        dest="ocr",
        action="store_true",
        default=True,
        help="Enable OCR (default)",
    )
    parser.add_argument(
        "--no-ocr",
        dest="ocr",
        action="store_false",
        help="Disable OCR",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(f"Input PDF not found: {input_path}")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    stem = input_path.stem
    markdown_path = out_dir / f"{stem}.md"
    text_path = out_dir / f"{stem}.txt"
    pdf_path = out_dir / f"{stem}.searchable.pdf"

    converter = _build_converter(args.lang, args.ocr)
    page_range = _parse_page_range(args.pages)
    result = converter.convert(str(input_path), page_range=page_range)
    document = result.document if hasattr(result, "document") else result

    markdown = document.export_to_markdown()
    markdown_path.write_text(markdown, encoding="utf-8")

    if hasattr(document, "export_to_text"):
        text = document.export_to_text()
    else:
        text = _markdown_to_text(markdown)
    text_path.write_text(text, encoding="utf-8")

    exported_pdf = None
    if hasattr(document, "export_to_pdf"):
        exported_pdf = document.export_to_pdf()
    if not _write_pdf(exported_pdf, pdf_path):
        pdf_path = None

    print(f"Markdown: {markdown_path}")
    print(f"Text: {text_path}")
    if pdf_path is not None:
        print(f"Searchable PDF: {pdf_path}")
    else:
        print("Searchable PDF: not available in this Docling version")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
