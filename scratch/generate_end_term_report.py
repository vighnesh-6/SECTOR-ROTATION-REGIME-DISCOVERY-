"""
scratch/generate_end_term_report.py
===================================
Generates the complete B.Tech CSE Machine Learning Final Project Report
for BML Munjal University following the official university template structure.

Outputs:
  - reports/end_term_report.docx
  - reports/final_project_report.docx
"""

import os
import sys
from pathlib import Path
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import parse_xml, OxmlElement
from docx.oxml.ns import nsdecls, qn

def set_cell_background(cell, fill_hex):
    """Set background color of a table cell."""
    tcPr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    tcPr.append(shd)

def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    """Set inner margins (padding) for a table cell (in twips, 20 twips = 1 pt)."""
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = parse_xml(f'<w:tcMar {nsdecls("w")}>'
                      f'<w:top w:w="{top}" w:type="dxa"/>'
                      f'<w:bottom w:w="{bottom}" w:type="dxa"/>'
                      f'<w:left w:w="{left}" w:type="dxa"/>'
                      f'<w:right w:w="{right}" w:type="dxa"/>'
                      f'</w:tcMar>')
    tcPr.append(tcMar)

def set_table_borders(table, color="D3D3D3", sz="4", val="single"):
    """Set clean subtle borders for a table."""
    tblPr = table._tbl.tblPr
    borders = parse_xml(f'<w:tblBorders {nsdecls("w")}>'
                        f'<w:top w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
                        f'<w:bottom w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
                        f'<w:left w:val="none"/>'
                        f'<w:right w:val="none"/>'
                        f'<w:insideH w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
                        f'<w:insideV w:val="none"/>'
                        f'</w:tblBorders>')
    tblPr.append(borders)

def format_run(run, font_name="Times New Roman", size_pt=12, bold=False, italic=False, color_rgb=(0,0,0)):
    """Apply standard typography to a text run."""
    run.font.name = font_name
    run.font.size = Pt(size_pt)
    run.bold = bold
    run.italic = italic
    run.font.color.rgb = RGBColor(*color_rgb)

def add_p(doc, text="", align=WD_ALIGN_PARAGRAPH.JUSTIFY, space_before=0, space_after=6, line_spacing=1.15, bold=False, italic=False, size_pt=12):
    """Add a body paragraph formatted in Times New Roman."""
    p = doc.add_paragraph()
    p.alignment = align
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.line_spacing = line_spacing
    if text:
        run = p.add_run(text)
        format_run(run, font_name="Times New Roman", size_pt=size_pt, bold=bold, italic=italic)
    return p

def add_heading_1(doc, text):
    """Add a Chapter / Major Heading (16 pt Bold Black)."""
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.space_before = Pt(16)
    p.paragraph_format.space_after = Pt(8)
    p.paragraph_format.keep_with_next = True
    run = p.add_run(text)
    format_run(run, font_name="Times New Roman", size_pt=16, bold=True)
    return p

def add_heading_2(doc, text):
    """Add a Section Heading (14 pt Bold Black)."""
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.keep_with_next = True
    run = p.add_run(text)
    format_run(run, font_name="Times New Roman", size_pt=14, bold=True)
    return p

def add_heading_3(doc, text):
    """Add a Subsection Heading (12 pt Bold Black)."""
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.keep_with_next = True
    run = p.add_run(text)
    format_run(run, font_name="Times New Roman", size_pt=12, bold=True)
    return p

def add_bullet_item(doc, bold_prefix, text):
    """Add a bullet item with a bold prefix."""
    p = doc.add_paragraph(style='List Bullet')
    p.paragraph_format.space_before = Pt(1)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.line_spacing = 1.15
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    r1 = p.add_run(bold_prefix)
    format_run(r1, font_name="Times New Roman", size_pt=12, bold=True)
    r2 = p.add_run(text)
    format_run(r2, font_name="Times New Roman", size_pt=12, bold=False)
    return p

def add_figure(doc, img_path, fig_num, caption, width_in=6.0):
    """Insert a centered figure with a professional 10 pt caption."""
    if os.path.exists(img_path):
        p_img = doc.add_paragraph()
        p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_img.paragraph_format.space_before = Pt(8)
        p_img.paragraph_format.space_after = Pt(4)
        run_img = p_img.add_run()
        run_img.add_picture(img_path, width=Inches(width_in))
        
        p_cap = doc.add_paragraph()
        p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_cap.paragraph_format.space_before = Pt(2)
        p_cap.paragraph_format.space_after = Pt(12)
        p_cap.paragraph_format.keep_with_next = False
        r1 = p_cap.add_run(f"Figure {fig_num}: ")
        format_run(r1, font_name="Times New Roman", size_pt=10, bold=True)
        r2 = p_cap.add_run(caption)
        format_run(r2, font_name="Times New Roman", size_pt=10, italic=True)
    else:
        print(f"Warning: Figure not found at {img_path}")

def add_code_block(doc, code_str, title=""):
    """Insert a code excerpt block formatted in Consolas 9.5 pt inside a shaded container."""
    if title:
        p_title = doc.add_paragraph()
        p_title.paragraph_format.space_before = Pt(6)
        p_title.paragraph_format.space_after = Pt(2)
        p_title.paragraph_format.keep_with_next = True
        r_t = p_title.add_run(title)
        format_run(r_t, font_name="Times New Roman", size_pt=10.5, bold=True)
        
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    
    cell = table.cell(0, 0)
    cell.width = Inches(6.2)
    set_cell_background(cell, "F8F9FA")
    set_cell_margins(cell, top=140, bottom=140, left=200, right=200)
    
    # Border
    tcPr = cell._tc.get_or_add_tcPr()
    tcBorders = parse_xml(f'<w:tcBorders {nsdecls("w")}>'
                          f'<w:top w:val="single" w:sz="6" w:space="0" w:color="E2E8F0"/>'
                          f'<w:left w:val="single" w:sz="18" w:space="0" w:color="3B82F6"/>'
                          f'<w:bottom w:val="single" w:sz="6" w:space="0" w:color="E2E8F0"/>'
                          f'<w:right w:val="single" w:sz="6" w:space="0" w:color="E2E8F0"/>'
                          f'</w:tcBorders>')
    tcPr.append(tcBorders)
    
    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.line_spacing = 1.05
    run = p.add_run(code_str.strip())
    format_run(run, font_name="Consolas", size_pt=9.0, color_rgb=(30, 41, 59))
    
    p_after = doc.add_paragraph()
    p_after.paragraph_format.space_before = Pt(0)
    p_after.paragraph_format.space_after = Pt(6)

print("Helper functions initialized.")
