"""Insert the contact-confidence result (030) into Chinese manuscript v19 -> v20.

Anchor is paragraph 115 by index (the inventory-error paragraph added by
patch_v19.py), so insertion does not depend on any CJK literal surviving an
encoding round trip.
"""
import glob
import json
import os
from copy import deepcopy

from docx import Document
from docx.text.paragraph import Paragraph

ROOT = r"D:/Project/imu环境重建/paper/2026-11-09-controlled-position-leakage-zh"
SRC = sorted(glob.glob(os.path.join(ROOT, "\u8bba\u6587\u521d\u7a3f_v19.docx")))[0]
DST = os.path.join(ROOT, "\u8bba\u6587\u521d\u7a3f_v20.docx")
ANCHOR = 115

BODY = (
    "\u63a5\u89e6\u7f6e\u4fe1\u5ea6\u4e5f\u4e0d\u5728\u4e8b\u4ef6\u957f\u77ed\u91cc\u3002"
    "\u628a\u540c\u4e00\u6761 14 \u8bbf\u6b21\u8bb0\u5f55\u91cc\u7684\u63a5\u89e6\u6309\u65f6\u957f\u4ece\u957f\u5230\u77ed\u6392\uff0c"
    "\u53ea\u7559\u6700\u957f\u7684 11\u30019\u30016 \u6b21\uff0c\u6574\u5c4b\u5206\u522b\u662f 4\u30010\u30010 \u95f4\uff1b"
    "\u540c\u6837\u6570\u91cf\u7684\u968f\u673a\u5b50\u96c6\uff08\u4e09\u4e2a\u79cd\u5b50\uff09\u5408\u8d77\u6765\u662f 19/36\u300117/36\u300114/36\uff0c"
    "F1 0.8026\u30010.7630\u30010.7422 \u5bf9 0.7786\u30010.6431\u30010.5486\u3002"
    "\u9010\u623f\u6bd4\uff0c6 \u6b21\u8fd9\u4e00\u6863\u5728 9 \u95f4\u623f\u6bd4\u81ea\u5df1\u7684\u968f\u673a\u5b50\u96c6\u5dee\u30012 \u95f4\u597d\u3002"
    "\u539f\u56e0\u5f88\u76f4\u767d\uff1a\u67dc\u5b50\u524d\u5f85\u5f97\u6700\u4e45\uff0c\u6309\u65f6\u957f\u6392\u7b49\u4e8e\u5148\u628a\u6905\u5b50\u4e0e\u5e8a\u4e22\u6389\uff0c"
    "6 \u6b21\u91cc\u5e73\u5747\u53ea\u5269 1.4 \u4e2a\u5750\u59ff\u63a5\u89e6\u3001\u4e00\u4e2a\u8eba\u59ff\u90fd\u6ca1\u6709\uff08\u968f\u673a\u662f 1.9 \u4e2a\uff09\u3002"
    "\u53e6\u5916\u4e24\u6761\u53ef\u4ee5\u5f53\u7f6e\u4fe1\u5ea6\u7684\u4fe1\u53f7\u5728\u73b0\u6709\u6570\u636e\u91cc\u4e5f\u4e0d\u6210\u7acb\uff1a"
    "\u4e09\u6b21\u5b9e\u73b0\u91cc 12 \u95f4\u623f\u7684 14 \u4e2a\u63a5\u89e6\u6309 80% \u65f6\u95f4\u91cd\u53e0\u5168\u90e8\u590d\u73b0\uff0c\u6ca1\u6709\u65b9\u5dee\uff1b"
    "\u8de8\u6a21\u6001\u4e00\u81f4\u53ea\u5bf9\u67dc\u5b50\u6709\u5b9a\u4e49\uff0c\u800c\u878d\u5408\u65f6\u624b\u673a\u4fa7\u67dc\u5b50\u88ab\u4e22\u5f03\u3002"
    "\u63a5\u89e6\u8d28\u91cf\u5728\u8fd9\u6761\u94fe\u4e0a\u662f\u7a7a\u95f4\u95ee\u9898\u3002"
)


def main():
    doc = Document(SRC)
    anchor = doc.paragraphs[ANCHOR]
    assert anchor.text.strip(), "anchor paragraph is empty"

    new_el = deepcopy(anchor._p)
    anchor._p.addnext(new_el)
    para = Paragraph(new_el, anchor._parent)
    for run in list(para.runs)[1:]:
        run._element.getparent().remove(run._element)
    para.runs[0].text = BODY

    tmp = os.path.join(ROOT, "_v20_tmp.docx")
    doc.save(tmp)
    os.replace(tmp, DST)
    print(json.dumps({"paragraphs": len(doc.paragraphs), "chars": len(BODY)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
