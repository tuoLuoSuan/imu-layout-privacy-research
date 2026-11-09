"""Build 论文初稿_v10.docx from v9: seven selection criteria across three batches."""
import copy
from pathlib import Path
from docx import Document
from docx.text.paragraph import Paragraph

HERE = Path(__file__).resolve().parent
SRC = HERE / '论文初稿_v9.docx'
DST = HERE / '论文初稿_v10.docx'

H410 = '4.10 选择准则没有复现出整屋增益'
P94 = ('4.8节把严重度零档的剩余损耗定位到覆盖与选择：32间里每个真值实例在截断池中都有中心误差不超过0.5 m的候选，'
       '把候选域限制到真值近邻后28间可行且全中，实际整屋全中是24间。这一节把真值无关的选择准则逐类试完，'
       '并在两个独立批次上对照。三批各32间：A为11500至11531、严重度零；B为11200至11231、同为严重度零，'
       '与4.7节之前的输入批次一致；C为11600至11631、严重度0.5并启用4.7节的陀螺跟踪。'
       '七类准则分别是候选保留上限降到64、集成共识（十次加噪解码取众数）、跨截断一致性、软覆盖、代价先验、'
       '区间残差容差，以及代价带内重排与精确最小代价；它们都只读候选池、接触事件、外框与清单尺寸。')
P95 = ('基线在A、B、C三批的整屋全中分别是24、23、17。批内最好的是A批的27间（代价先验λ等于1，B批为23不变）'
       '与26间（代价带内重排加候选上限64；B批23不变，配对为3比1，精确McNemar p=0.625，合并64间47到49）。'
       '能稳定复现的只有候选上限64：A批25、C批18，各加1间，B批23不变；代价先验在A批加的3间恰好都是纯选择失败的三间，'
       '换一批就归零。反过来，把"首个可行解"换成"带内最小代价"更差，A批降到22间（上限128）与25间（上限64）。'
       '软覆盖允许丢掉少量事件后32间全部可解，但整屋只剩23间——它把冲突换成了可行，而不是正确。')
P96 = ('因此这一层与4.9节的结论正好互补：证据质量能移动整屋率（慢变陀螺0/12在门控跟踪下回到5/12，'
       '严重度0.5档在合并64间上由25回到34），解码准则不能。剩余8间不是"没选对准则"，'
       '而是现有的接触事件与轨迹不足以把真值解与近邻解区分开，杠杆在上游证据。'
       '边界是每批32间：在这个规模上McNemar功效很低，批内加2到3间既不能写成提升，跨批归零也不能写成准则必然无效；'
       '能说的是在这条链与这些批次上，没有一类准则给出可复现的整屋增益。')

CONC_OLD = '同样幅度、不同时间结构的对照给出另一条边界：慢变陀螺误差使12间全部失去命中，而门控陀螺跟踪在不改动无扰动档的前提下取回5/12。'
CONC_NEW = CONC_OLD + '在解码一侧，七类真值无关的选择准则没有一个能在独立批次上复现整屋增益，说明这一层的限制在证据而不在准则。'


def set_text(p, text):
    for r in p.runs[1:]:
        r.text = ''
    if p.runs:
        p.runs[0].text = text
    else:
        p.add_run(text)


def para(doc, start):
    return next(p for p in doc.paragraphs if ''.join(r.text for r in p.runs).startswith(start))


def insert_after(p, style, text):
    new = copy.deepcopy(p._p)
    p._p.addnext(new)
    np_ = Paragraph(new, p._parent)
    set_text(np_, text)
    np_.style = style
    return np_


def main():
    doc = Document(str(SRC))
    cursor = para(doc, '有效的做法是估计而不是假设。')
    cursor = insert_after(cursor, 'Heading 2', H410)
    for text in [P94, P95, P96]:
        cursor = insert_after(cursor, 'Body Text', text)

    conc = para(doc, '在已知外框和家具清单尺寸的受控单间中')
    tc = conc.runs[0].text
    assert CONC_OLD in tc, 'conclusion anchor missing'
    conc.runs[0].text = tc.replace(CONC_OLD, CONC_NEW)

    doc.save(str(DST))
    print('saved', DST)


if __name__ == '__main__':
    main()
