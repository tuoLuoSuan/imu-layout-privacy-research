import glob, os, shutil
from copy import deepcopy

import docx
from docx.text.paragraph import Paragraph

src = glob.glob("paper/2026-11-09-controlled-position-leakage-zh/*v22.docx")[0]
doc = docx.Document(src)
ps = doc.paragraphs
assert ps[117].text.strip().startswith("在同一条14"), ps[117].text[:20]

text = ("在固定录音这一层，我们把类别配额也固定住再选。每间房取 6 个接触，按可用的坐姿、躺姿、"
        "柜子事件数量分配，每类至少一个；这 24 间房的配额都是 2/2/2。配额固定之后，空间分散的那一组"
        "在从未见过的确认批 11700 至 11711 上明显好于同配额的随机：9 间变好、1 间变差、2 间持平，"
        "F1 平均高 0.0899，整屋 7/12 对 16/36。开发批 12 间的方向一致（+0.0503，5 好 3 差 4 平）。"
        "但配额本身不是收益来源：同配额随机与不限配额随机的差别在开发批上是 +0.0700、在确认批上是 "
        "−0.0122，量级都小于分散效应。按真值类别给每件物体取最近接触的那一组在两个批上都低于随机（0.6806、"
        "0.7252），所以它不是上界。6 个接触无论怎么挑，仍然低于 14 次的整段（确认批 0.8829 对 0.9603）。"
        "每批只有 12 间房、单一严重度与单一 k，这些符号计数只作描述。")

template = ps[117]
el = deepcopy(template._p)
template._p.addnext(el)
newp = Paragraph(el, template._parent)
for r in newp.runs:
    r.text = ""
newp.runs[0].text = text if newp.runs else None
for r in newp.runs[1:]:
    r.text = ""

dst = "paper/2026-11-09-controlled-position-leakage-zh/论文初稿_v23.docx"
doc.save(dst)
print("saved", dst, os.path.getsize(dst))
