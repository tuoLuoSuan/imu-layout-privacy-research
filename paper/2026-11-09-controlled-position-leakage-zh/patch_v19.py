import glob, os
from copy import deepcopy
from docx import Document
from docx.text.paragraph import Paragraph

SRC = sorted(glob.glob('paper/2026-11-09-controlled-position-leakage-zh/*v18.docx'))[0]
DST = os.path.join(os.path.dirname(SRC), '论文初稿_v19.docx')
doc = Document(SRC)

def copy_font(target, source):
    if not source.runs:
        return
    s = source.runs[0]
    r = target.runs[-1]
    if s.font.name: r.font.name = s.font.name
    if s.font.size: r.font.size = s.font.size
    r.font.bold = s.font.bold

# 1) abstract sentence
abs_para = doc.paragraphs[4]
assert abs_para.style.name == 'Abstract', abs_para.style.name
abs_para.add_run('把录音固定、只削接触数的对照说明这段增益主要来自接触数；把接触数固定、把录音拉长到 20 访次，整屋只多 1 间。')
copy_font(abs_para, abs_para)

# 2) insert after paragraph 111
anchor = doc.paragraphs[111]
assert anchor.text.startswith('旧协议的单次实现'), anchor.text[:20]
NEW = [
 '把预算与选择拆开。前面两节各改一个变量，这里把两条受控对照放在一起说。第一条把录音固定：同一段 14 访次记录、把合格接触削到 6 次，14 次的整屋是 7/12（实例 F1 0.8135），前 6 次 4/12（0.7274），按最远点分散取的 6 次 5/12（0.7028），随机 6 次 8/36（0.6435），允许看真值身份挑的 6 次 4/12（0.7960）。同样时长下，8 个接触值 3 间房；选哪 8 个只把平均 F1 改动最多 0.07，换不动整屋。',
 '第二条把接触数固定：把录音拉长到 20 访次、接触仍取 14，整屋 8/12，与用满 20 次接触相同，分散取与真值协助的 14 次也各是 8/12。超过 14 次以后多余接触不再加分，更长的记录最多只多 1 间。两条合起来，网格里 6 到 14 访次的增益主要是接触数带来的，固定接触数下把记录拉长只值 1 间房。',
 '出解不等于对。324 行里解码器给出解的有 266 行（82.1%），整屋全中 156 行（48.1%）；出解但仍然错的 110 行，这些行里每个声明件都摆得自洽，只是至少漏一件。缺口集中在无扰动档：108 行里 105 行出解、62 行全中、43 行自洽而错。不出解的 58 行全部不中，其中 45 行 proposal_conflict、11 行搜索预算耗尽、2 行候选池为空。出解率与恢复率回答的是两个问题，必须分开报。',
 '清单错了不是小扰动。在同一批 12 间上只改声明清单，前端、精修、候选上限 128 与支撑代价 0.3 都不动：正确五件时整屋 7/12、F1 0.8135、放下 4.58/5；声明里没有柜子时只剩四件、放下 1.08/4、9 间房 proposal_conflict；两个椅子并成一个时四件、放下 2.33/4、5 间房 proposal_conflict。两个编辑臂的整屋全中按构造为 0（真值里仍有被删掉的那件），所以损失要按可行性报：多数房间根本不出解，而不是位置偏几厘米。',
 '先验对照的第二个独立批次。在 11200 至 11231 上只给房间外框、起点与清单，整屋仍 0/32、平均 F1 0.0793；该批自己存储的原始臂是 21/32、0.8013；配对差 21 间、房间自助 95% 区间 [50.0, 81.3] 个百分点、精确 McNemar p=9.5e-7。两批分开报告，不合并。',
]
template = anchor
last = anchor
for text in NEW:
    el = deepcopy(template._p)
    last._p.addnext(el)
    para = Paragraph(el, template._parent)
    for r in list(para.runs):
        r._element.getparent().remove(r._element)
    para.add_run(text)
    copy_font(para, template)
    last = para

doc.save(DST)
print('saved', DST, 'paras', len(Document(DST).paragraphs))
