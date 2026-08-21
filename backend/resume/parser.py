"""
Resume parser — extracts structured data from PDF/DOCX files.
Uses PyMuPDF (fitz) for PDF and python-docx for Word documents.
"""

import io
import re
import logging
from typing import IO

logger = logging.getLogger(__name__)


class ResumeParser:

    def parse(self, file_content: bytes, filename: str) -> dict:
        """Parse resume file and return structured JSON."""
        ext = filename.rsplit(".", 1)[-1].lower()
        if ext == "pdf":
            text = self._extract_pdf_text(file_content)
        elif ext in ("doc", "docx"):
            text = self._extract_docx_text(file_content)
        else:
            raise ValueError(f"Unsupported file format: {ext}")

        return self._structure_text(text)

    def _extract_pdf_text(self, content: bytes) -> str:
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(stream=content, filetype="pdf")
            return "\n".join(page.get_text() for page in doc)
        except ImportError:
            raise RuntimeError("PyMuPDF not installed. Run: pip install pymupdf")

    def _extract_docx_text(self, content: bytes) -> str:
        try:
            from docx import Document
            doc = Document(io.BytesIO(content))
            return "\n".join(para.text for para in doc.paragraphs)
        except ImportError:
            raise RuntimeError("python-docx not installed. Run: pip install python-docx")

    def _structure_text(self, text: str) -> dict:
        """
        Naive section-based parser.
        In production, augment with an LLM extraction call for higher accuracy.
        """
        sections = {
            "raw_text":   text,
            "skills":     self._extract_skills(text),
            "experience": self._extract_section(text, ["experience", "work history"]),
            "education":  self._extract_section(text, ["education", "academic"]),
            "projects":   self._extract_section(text, ["projects", "portfolio"]),
            "summary":    self._extract_section(text, ["summary", "objective", "profile"]),
        }
        return sections

    def _extract_skills(self, text: str) -> list[str]:
        common_tech = [
            "python", "javascript", "typescript", "java", "golang", "rust", "c++",
            "react", "next.js", "node.js", "fastapi", "django", "flask",
            "postgresql", "mysql", "mongodb", "redis", "elasticsearch",
            "docker", "kubernetes", "aws", "gcp", "azure", "terraform",
            "git", "ci/cd", "microservices", "rest api", "graphql",
        ]
        text_lower = text.lower()
        return [skill for skill in common_tech if skill in text_lower]

    def _extract_section(self, text: str, keywords: list[str]) -> str:
        lines = text.split("\n")
        collecting = False
        section_lines = []

        for i, line in enumerate(lines):
            line_lower = line.lower().strip()
            if any(kw in line_lower for kw in keywords) and len(line_lower) < 60:
                collecting = True
                continue
            if collecting:
                # Stop at next major section heading (all caps or short line)
                if line.isupper() and len(line.strip()) > 3 and len(line.strip()) < 40:
                    break
                section_lines.append(line)

        return "\n".join(section_lines[:30]).strip()  # cap at 30 lines
