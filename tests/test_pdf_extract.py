import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pdf_extract import extract_pdf, save_result


class PdfExtractionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.pdf = self.root / "sample.pdf"
        with pymupdf.open() as document:
            page = document.new_page()
            page.insert_text((72, 72), "Project A: target 120; actual 105 cases.")
            page.insert_text((72, 150), "Source note: provisional figures.")
            document.new_page()  # 빈 페이지를 정상 추출로 오인하지 않아야 한다.
            document.set_page_labels([{"startpage": 0, "prefix": "Appendix-", "style": "D", "firstpagenum": 1}])
            document.save(self.pdf)

    def tearDown(self):
        self.temp.cleanup()

    def test_page_provenance_and_unverified_labels(self):
        result = extract_pdf(self.pdf)
        self.assertEqual(result.document.page_count, 2)
        self.assertEqual(result.document.version_sha256, hashlib.sha256(self.pdf.read_bytes()).hexdigest())
        self.assertEqual([page.pdf_page for page in result.pages], [1, 2])
        self.assertIn("actual 105", result.pages[0].text)
        self.assertIsNone(result.pages[0].printed_page_label)
        self.assertEqual(result.pages[0].metadata["pdf_page_label"], "Appendix-1")
        self.assertEqual(result.pages[1].metadata["extraction_status"], "no_native_text")
        self.assertTrue(result.pages[1].metadata["needs_review"])

    def test_blocks_refer_to_actual_source_text(self):
        result = extract_pdf(self.pdf)
        ids = [block.block_id for block in result.blocks]
        self.assertEqual(len(ids), len(set(ids)))
        with pymupdf.open(self.pdf) as original:
            for block in result.blocks:
                self.assertEqual(block.doc_id, result.document.doc_id)
                self.assertEqual(block.source_locator["pdf_page"], block.pdf_page)
                text = original[block.pdf_page - 1].get_textbox(pymupdf.Rect(block.source_locator["bbox"]))
                self.assertEqual("".join(text.split()), "".join(block.text.split()))
                self.assertEqual(block.verification_status, "unverified")

    def test_identical_content_retains_document_and_block_ids(self):
        other = self.root / "renamed.pdf"
        shutil.copyfile(self.pdf, other)
        first, second = extract_pdf(self.pdf), extract_pdf(other)
        self.assertEqual(first.document.doc_id, second.document.doc_id)
        self.assertEqual([b.block_id for b in first.blocks], [b.block_id for b in second.blocks])

    def test_same_name_different_content_has_separate_output(self):
        other = self.root / "other" / "sample.pdf"
        other.parent.mkdir()
        with pymupdf.open() as document:
            page = document.new_page()
            page.insert_text((72, 72), "Different document")
            document.save(other)
        output = self.root / "processed"
        first = save_result(extract_pdf(self.pdf), output)
        second = save_result(extract_pdf(other), output)
        self.assertNotEqual(first, second)
        self.assertTrue((first / "pages.jsonl").is_file())

    def test_jsonl_outputs_keyword_and_repeat_run(self):
        result = extract_pdf(self.pdf)
        output = save_result(result, self.root / "out", keyword="target 120")
        pages = [json.loads(line) for line in (output / "pages.jsonl").read_text().splitlines()]
        self.assertEqual(len(pages), result.document.page_count)
        self.assertEqual(json.loads((output / "summary.json").read_text())["keyword_candidate_pages"], [1])
        self.assertIn("target 120", (output / "candidate_pages.txt").read_text())
        self.assertIn("[PDF page 2]", (output / "output.txt").read_text())
        save_result(result, self.root / "out")
        self.assertEqual((output / "candidate_pages.txt").read_text(), "")

    def test_optional_split_pages_preserves_each_page(self):
        output = save_result(extract_pdf(self.pdf), self.root / "out", split_pages=True)
        for number in [1, 2]:
            with pymupdf.open(output / "pages" / f"page_{number:04d}.pdf") as single:
                self.assertEqual(single.page_count, 1)
                self.assertEqual(bool(single[0].get_text().strip()), number == 1)

    def test_reject_html_and_password_protected_pdf(self):
        html = self.root / "download.pdf"
        html.write_text("<html>This is not a PDF</html>")
        with self.assertRaisesRegex(ValueError, "PDF 헤더"):
            extract_pdf(html)
        protected = self.root / "protected.pdf"
        with pymupdf.open(self.pdf) as document:
            document.save(protected, encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="secret", owner_pw="owner")
        with self.assertRaisesRegex(ValueError, "암호"):
            extract_pdf(protected)

    def test_image_only_page_is_reported_without_invented_text(self):
        with pymupdf.open(self.pdf) as original:
            png = original[0].get_pixmap().tobytes("png")
        scanned = self.root / "scanned.pdf"
        with pymupdf.open() as document:
            page = document.new_page()
            page.insert_image(page.rect, stream=png)
            document.save(scanned)
        result = extract_pdf(scanned)
        self.assertEqual(result.pages[0].char_count, 0)
        self.assertEqual(result.pages[0].metadata["extraction_status"], "no_native_text")
        self.assertEqual(result.blocks, [])

    def test_batch_continues_after_bad_pdf_and_supports_uppercase_extension(self):
        folder = self.root / "input"
        folder.mkdir()
        shutil.copyfile(self.pdf, folder / "good.PDF")
        (folder / "bad.pdf").write_text("not a PDF")
        process = subprocess.run(
            [sys.executable, str(ROOT / "01_extract_pdf.py"), "--file-dir", str(folder), "--out", str(self.root / "out")],
            cwd=self.root, capture_output=True, text=True,
        )
        self.assertEqual(process.returncode, 1, process.stderr)
        report = json.loads(process.stdout)
        self.assertEqual(len(report["documents"]), 1)
        self.assertEqual(len(report["errors"]), 1)


if __name__ == "__main__":
    unittest.main()
