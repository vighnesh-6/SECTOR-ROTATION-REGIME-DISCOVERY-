"""
scratch/convert_to_pdf.py
=========================
Converts the generated DOCX report to PDF using Microsoft Word.
"""

import os
import win32com.client

def convert_docx_to_pdf(docx_path, pdf_path):
    word = win32com.client.Dispatch("Word.Application")
    word.Visible = False
    in_file = os.path.abspath(docx_path)
    out_file = os.path.abspath(pdf_path)
    print(f"Converting {in_file} -> {out_file}...")
    doc = word.Documents.Open(in_file)
    doc.SaveAs(out_file, FileFormat=17) # 17 = wdFormatPDF
    doc.Close()
    word.Quit()
    print(f"Successfully generated {pdf_path} (Size: {os.path.getsize(out_file)} bytes)")

if __name__ == "__main__":
    convert_docx_to_pdf("reports/end_term_report.docx", "reports/end_term_report.pdf")
    # Also copy or convert to final_project_report.pdf
    import shutil
    shutil.copyfile("reports/end_term_report.pdf", "reports/final_project_report.pdf")
    print("Successfully copied to reports/final_project_report.pdf")
