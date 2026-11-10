# -*- coding: utf-8 -*-
"""v13b: caption of figure 7 follows the corrected grid result."""
from pathlib import Path
import docx
HERE = Path(__file__).resolve().parent
p = HERE / "论文初稿_v13.docx"
doc = docx.Document(str(p))
ps = doc.paragraphs
cap = ps[110]
assert cap.text.startswith("图7"), cap.text[:20]
new = ("图7 活动预算与证据质量。12间房上访次与严重度的3×3配对网格，格内为恢复间数，边注为百分点差。"
       "第一轮的质量轴为11对2、预算轴6对3，但每个条件都在同一批房间内重复，按房间聚类后两条轴均不显著（p=0.133与p=0.656）；"
       "改用前缀一致的噪声重跑后严重度方向翻转（4/5/7、5/6/6、7/7/6，−8.33与+11.11个百分点），108格中有33格改变。")
for r in cap.runs[1:]:
    r.text = ""
(cap.runs[0] if cap.runs else cap.add_run()).text = new
doc.save(str(p))
print("caption updated")