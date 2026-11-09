import re, sys
from pathlib import Path
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.section import WD_SECTION
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.enum.table import WD_TABLE_ALIGNMENT

HERE = Path(__file__).resolve().parent
SRC = HERE / 'manuscript.md'
OUT = HERE / 'cvpr2026.docx'
WIDE = ('fig1', 'fig6')
WIDTH = {'fig1': 7.0, 'fig2': 3.4, 'fig3': 3.4, 'fig4': 3.4, 'fig5': 3.4, 'fig6': 7.0}


def sect_break(paragraph, ncols):
    pPr = paragraph._p.get_or_add_pPr()
    sectPr = OxmlElement('w:sectPr')
    cols = OxmlElement('w:cols')
    cols.set(qn('w:num'), str(ncols))
    cols.set(qn('w:space'), '360')
    sectPr.append(cols)
    pPr.append(sectPr)


def set_doc_cols(section, ncols):
    sectPr = section._sectPr
    cols = sectPr.find(qn('w:cols'))
    if cols is None:
        cols = OxmlElement('w:cols')
        sectPr.append(cols)
    cols.set(qn('w:num'), str(ncols))
    cols.set(qn('w:space'), '360')


def style_font(doc, name='Times New Roman', size=10):
    st = doc.styles['Normal']
    st.font.name = name
    st.font.size = Pt(size)
    st.element.rPr.rFonts.set(qn('w:eastAsia'), name)
    pf = st.paragraph_format
    pf.space_after = Pt(3)
    pf.space_before = Pt(0)
    pf.line_spacing = 1.0


def add_runs(p, text, size=None, italic=False):
    for k, seg in enumerate(re.split(r'\*\*(.+?)\*\*', text)):
        if not seg:
            continue
        r = p.add_run(seg)
        r.bold = (k % 2 == 1)
        r.italic = italic
        if size:
            r.font.size = Pt(size)


def para(doc, text, size=10, align='justify', space_after=3, first_indent=0, left_indent=0):
    p = doc.add_paragraph()
    p.alignment = {'justify': WD_ALIGN_PARAGRAPH.JUSTIFY, 'center': WD_ALIGN_PARAGRAPH.CENTER,
                   'left': WD_ALIGN_PARAGRAPH.LEFT}[align]
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.first_line_indent = Inches(first_indent)
    p.paragraph_format.left_indent = Inches(left_indent)
    add_runs(p, text, size=size)
    return p


def heading(doc, text, size=11, space_before=9, space_after=3):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.keep_with_next = True
    r = p.add_run(text)
    r.bold = True
    r.font.size = Pt(size)
    return p


def add_table(doc, header, rows, caption):
    cap = doc.add_paragraph()
    cap.paragraph_format.space_before = Pt(6)
    cap.paragraph_format.space_after = Pt(2)
    cap.paragraph_format.keep_with_next = True
    r = cap.add_run(caption)
    r.font.size = Pt(8)
    t = doc.add_table(rows=1 + len(rows), cols=len(header))
    t.style = 'Table Grid'
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for j, h in enumerate(header):
        cell = t.rows[0].cells[j]
        cell.text = ''
        run = cell.paragraphs[0].add_run(h)
        run.bold = True
        run.font.size = Pt(8)
        cell.paragraphs[0].paragraph_format.space_after = Pt(0)
    for i, row in enumerate(rows):
        for j, v in enumerate(row):
            cell = t.rows[i + 1].cells[j]
            cell.text = ''
            run = cell.paragraphs[0].add_run(v)
            run.font.size = Pt(8)
            cell.paragraphs[0].paragraph_format.space_after = Pt(0)
    for row in t.rows:
        for cell in row.cells:
            tcPr = cell._tc.get_or_add_tcPr()
            borders = OxmlElement('w:tcBorders')
            for edge in ('top', 'left', 'bottom', 'right'):
                el = OxmlElement('w:' + edge)
                el.set(qn('w:val'), 'nil')
                borders.append(el)
            tcPr.append(borders)
    return t


def parse(md):
    lines = md.splitlines()
    i = 0
    if lines[0].strip() == '---':
        while lines[i].strip() != '---' or i == 0:
            i += 1
        i += 1
    blocks = []
    while i < len(lines):
        line = lines[i].rstrip()
        if not line.strip():
            i += 1
            continue
        m = re.match(r'!\[(.*?)\]\((.*?)\)(?:\{width=([\d.]+)%\})?$', line)
        if m:
            blocks.append(('img', m.group(2), m.group(1)))
            i += 1
            continue
        if line.startswith('| '):
            rows = []
            while i < len(lines) and lines[i].startswith('|'):
                cells = [c.strip() for c in lines[i].strip().strip('|').split('|')]
                if not all(re.match(r'^-{2,}$', c) for c in cells):
                    rows.append(cells)
                i += 1
            blocks.append(('table', rows[0], rows[1:]))
            continue
        if line.startswith('# '):
            blocks.append(('h1', line[2:].strip()))
            i += 1
            continue
        if line.startswith('## '):
            blocks.append(('h2', line[3:].strip()))
            i += 1
            continue
        if line.startswith(': Table'):
            blocks.append(('cap', line[2:].strip()))
            i += 1
            continue
        blocks.append(('p', line.strip()))
        i += 1
    return blocks


def main():
    blocks = parse(SRC.read_text(encoding='utf-8'))
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Inches(8.5), Inches(11)
    for a in ('left_margin', 'right_margin', 'top_margin', 'bottom_margin'):
        setattr(sec, a, Inches(0.75))
    set_doc_cols(sec, 2)
    style_font(doc)

    title = 'What Inertial Recordings Reveal About Furniture Layout: Contact Placement, Visit Count, and Sensor Error'
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(10)
    r = p.add_run(title)
    r.bold = True
    r.font.size = Pt(16)
    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub.paragraph_format.space_after = Pt(12)
    sr = sub.add_run('Anonymous CVPR submission')
    sr.font.size = Pt(10)
    sr.italic = True

    fig_no = 0
    WIDTH = {'fig1': 3.35, 'fig2': 3.35, 'fig3': 3.35, 'fig4': 3.35, 'fig5': 3.35, 'fig6': 3.35}
    in_front = True
    for b in blocks:
        kind = b[0]
        if kind == 'h1':
            text = b[1]
            if text.lower() == 'references':
                heading(doc, 'References', size=10, space_before=10)
                continue
            heading(doc, text, size=10)
        elif kind == 'h2':
            heading(doc, b[1], size=11, space_before=10)
        elif kind == 'cap':
            pass
        elif kind == 'p':
            para(doc, b[1], size=10, first_indent=0.0)
        elif kind == 'img':
            path, alt = b[1], b[2]
            key = Path(path).name.split('_')[0]
            width = WIDTH.get(key, 3.35)
            fig_no += 1
            img = HERE / path
            if not img.exists():
                img = HERE.parent / path
            ip = doc.add_paragraph()
            ip.alignment = WD_ALIGN_PARAGRAPH.CENTER
            ip.paragraph_format.space_before = Pt(4)
            ip.paragraph_format.space_after = Pt(2)
            ip.paragraph_format.keep_with_next = True
            ip.add_run().add_picture(str(img), width=Inches(width))
            cp = doc.add_paragraph()
            cp.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            cp.paragraph_format.space_after = Pt(8) if in_front else Pt(5)
            cr = cp.add_run('Figure %d. %s' % (fig_no, alt))
            cr.font.size = Pt(8.5)
            in_front = False
        elif kind == 'table':
            add_table(doc, b[1], b[2], 'Table 1. Whole-room recovery on 1,000 development rooms at four operating points of the layer-1 decoder. Tolerance is the per-class centre window; contacts is the number of interactions per room.')
    set_doc_cols(doc.sections[-1], 2)
    doc.save(str(OUT))
    print('saved', OUT, 'blocks', len(blocks))


main()
