#!/usr/bin/env python
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

import pdfplumber

SKIP_PHRASES = (
    "Essential Cybersecurity Controls",
    "Sharing Indicator",
    "Document Classification",
    "Unclassified",
    "Figure",
    "Table",
    "ECC",
)


def clean_line(line: str) -> str:
    line = line.replace("\u00ad", "")  # soft hyphen
    line = re.sub(r"\s+", " ", line).strip()
    return line


def is_header_or_footer(line: str) -> bool:
    if not line:
        return True
    if line.isdigit():
        return True
    for phrase in SKIP_PHRASES:
        if phrase in line and len(line.split()) < 8:
            return True
    return False


def parse_pdf(path: Path) -> tuple[list[dict], list[str]]:
    report = []
    controls = []

    main_domain = None
    subdomain_code = None
    subdomain_name = None
    objective_lines = []
    mode = None
    current_code = None
    current_text = []
    pending_prefix = []

    in_details = False

    with pdfplumber.open(str(path)) as pdf:
        for page_idx, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            lines = [clean_line(l) for l in text.splitlines()]
            for line in lines:
                if "Details of the Essential Cybersecurity Controls" in line:
                    in_details = True
                    report.append(f"Page {page_idx}: Entered control details section")
                    continue

                if is_header_or_footer(line):
                    continue

                if not in_details:
                    continue

                # main domain: "1 Cybersecurity Governance"
                m_main = re.match(r"^(\d+)\s+([A-Za-z].+)$", line)
                if m_main and not re.match(r"^\d+-\d+", line):
                    main_domain = m_main.group(2)
                    report.append(f"Page {page_idx}: Main domain {m_main.group(1)} - {main_domain}")
                    continue

                # subdomain: "1-1 Cybersecurity Strategy"
                m_sub = re.match(r"^(\d+-\d+)\s+(.+)$", line)
                if m_sub:
                    # save previous control
                    if current_code:
                        controls.append(
                            build_control(
                                code=current_code,
                                subdomain_code=subdomain_code,
                                subdomain_name=subdomain_name,
                                objective=" ".join(objective_lines).strip(),
                                text=" ".join(current_text).strip(),
                            )
                        )
                        current_code = None
                        current_text = []

                    subdomain_code = m_sub.group(1)
                    subdomain_name = m_sub.group(2)
                    objective_lines = []
                    mode = None
                    report.append(f"Page {page_idx}: Subdomain {subdomain_code} - {subdomain_name}")
                    continue

                if line.lower() == "objective":
                    mode = "objective"
                    objective_lines = []
                    continue
                if line.lower() == "controls":
                    mode = "controls"
                    continue

                # control code: "1-1-1 ..." or "1-5-1 a ..."
                m_ctrl = re.match(r"^(\d+-\d+-\d+)(?:\s+([a-z])(?=\s|$))?\s*(.*)$", line)
                if m_ctrl and mode == "controls":
                    if current_code:
                        controls.append(
                            build_control(
                                code=current_code,
                                subdomain_code=subdomain_code,
                                subdomain_name=subdomain_name,
                                objective=" ".join(objective_lines).strip(),
                                text=" ".join(current_text).strip(),
                            )
                        )
                    suffix = m_ctrl.group(2) or ""
                    current_code = f"{m_ctrl.group(1)}{suffix}".strip()
                    current_text = []
                    if pending_prefix:
                        current_text.append(" ".join(pending_prefix).strip())
                        pending_prefix = []
                    rest = m_ctrl.group(3).strip()
                    if rest:
                        current_text.append(rest)
                    continue

                if mode == "objective":
                    if line:
                        objective_lines.append(line)
                    continue

                if mode == "controls":
                    if current_code:
                        current_text.append(line)
                    else:
                        pending_prefix.append(line)

    # finalize last control
    if current_code:
        controls.append(
            build_control(
                code=current_code,
                subdomain_code=subdomain_code,
                subdomain_name=subdomain_name,
                objective=" ".join(objective_lines).strip(),
                text=" ".join(current_text).strip(),
            )
        )

    deduped = {}
    for item in controls:
        code = item["code"]
        existing = deduped.get(code)
        if not existing or len(item.get("description_en", "")) > len(existing.get("description_en", "")):
            deduped[code] = item
        else:
            report.append(f"Duplicate control ignored: {code}")

    return list(deduped.values()), report


def build_control(code: str, subdomain_code: str | None, subdomain_name: str | None, objective: str, text: str) -> dict:
    title_en = text
    if len(title_en) > 120:
        title_en = text.split(".")[0][:120]
    if not title_en:
        title_en = f"Control {code}"
    return {
        "category_ar": "",
        "category_en": subdomain_name or "",
        "category_code": subdomain_code or "",
        "code": f"NCA-ECC-{code}",
        "title_ar": "",
        "title_en": title_en.strip(),
        "risk_level": "MEDIUM",
        "required_evidence": "",
        "description_ar": "",
        "description_en": text.strip(),
    }


def write_outputs(controls: list[dict], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "nca_controls_seed.json"
    csv_path = out_dir / "nca_controls_seed.csv"

    with json_path.open("w", encoding="utf-8") as f:
        json.dump(controls, f, ensure_ascii=False, indent=2)

    fieldnames = [
        "category_ar",
        "category_en",
        "category_code",
        "code",
        "title_ar",
        "title_en",
        "risk_level",
        "required_evidence",
        "description_ar",
        "description_en",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in controls:
            writer.writerow(row)


def write_report(report_lines: list[str], controls: list[dict], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "parsing_report.txt"
    with report_path.open("w", encoding="utf-8") as f:
        f.write(f"Total controls parsed: {len(controls)}\n")
        f.write(f"Unique categories: {len(set(c['category_en'] for c in controls))}\n")
        f.write("----\n")
        for line in report_lines:
            f.write(line + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", required=True, help="Path to NCA controls PDF")
    parser.add_argument("--out-dir", default="cybertrust/apps/controls/data", help="Output directory")
    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        raise SystemExit(f"PDF not found: {pdf_path}")

    controls, report = parse_pdf(pdf_path)
    out_dir = Path(args.out_dir)
    write_outputs(controls, out_dir)
    write_report(report, controls, out_dir)
    print(f"Parsed {len(controls)} controls into {out_dir}")


if __name__ == "__main__":
    main()
