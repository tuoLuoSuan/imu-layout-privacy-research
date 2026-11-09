"""Build 论文初稿_v11.docx from v10: budget x evidence-quality paired matrix."""
import copy
from pathlib import Path
from docx import Document
from docx.text.paragraph import Paragraph

HERE = Path(__file__).resolve().parent
SRC = HERE / '论文初稿_v10.docx'
DST = HERE / '论文初稿_v11.docx'

H411 = '4.11 活动预算与证据质量：同一批房间上的配对网格'
P97 = ('4.9节在固定预算下改传感器谱形，4.10节在固定传感器下改选择准则；要检验"接触落点比交互次数更决定"这一说法，'
       '需要把预算与质量放在同一批房间、同一条链上。因此在12间（11500至11511）上做3乘3的配对网格：访次取6、10、14，'
       '严重度取0、0.5、1，共108格，每格单独重生成一遍。路线覆盖率在每一格都是1.0，即走过哪些可达格不变，'
       '变的只是重复访问与接触的次数（每格事件数中位数分别为82、95、108）。链路仍是门控陀螺跟踪、段位移前端、'
       '接触回访、储物墙距修复与声明先验解码；严重度零时门控不触发，与冻结链逐项相同。')
P98 = ('九格的整屋全中（6、10、14次乘严重度0、0.5、1，每格12间）分别是7、6、3与7、6、6与8、7、4；'
       '实例位置F1分别是0.897、0.702、0.530与0.885、0.726、0.560与0.808、0.722、0.465。按房间配对比较：'
       '把严重度从0提到1，6次与14次两档各丢4间（4比0），10次丢1间（3比2），三档合并11比2、+25.0个百分点、'
       '精确McNemar p=0.0225；把访次从6提到14，三档各多约一间（2比1、1比0、3比2），合并6比3、+8.3个百分点、p=0.51。')
P99 = ('访次没有换来判别力：严重度零一列的F1反而随访次下降（0.897、0.885、0.808）。新增的多是同一操作面的近似重复接触，'
       '既不能分开同类的多个候选，也不改变不重叠兼容约束下的可行集，只会把等价类做大；这与4.6节把先验放进候选集会剪掉'
       '近似正确框、4.10节七类准则不能复现增益是同一件事——命中与否取决于证据能否把真值解与近邻解分开。'
       '九格也不是一张曲面：10次严重度1的6/12高于14次严重度1的4/12，12间单次实现下格间差异含实现成分。'
       '边界还包括：每格只有12间配对、预算同时改变了记录时长（14次约620秒），以及严重度是合成生成器上的刻度，'
       '与真实器件的谱形没有对应关系。')

CONC_OLD = '说明这一层的限制在证据而不在准则。'
CONC_NEW = CONC_OLD + '把预算与质量放进同一批房间后，两条轴的差别也是可复现的：访次由6提到14只多3间（p=0.51），严重度由0提到1少9间（p=0.0225）。'


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
    cursor = para(doc, '因此这一层与4.9节的结论正好互补')
    cursor = insert_after(cursor, 'Heading 2', H411)
    for text in [P97, P98, P99]:
        cursor = insert_after(cursor, 'Body Text', text)

    conc = para(doc, '在已知外框和家具清单尺寸的受控单间中')
    hit = False
    for r in conc.runs:
        if CONC_OLD in r.text:
            r.text = r.text.replace(CONC_OLD, CONC_NEW)
            hit = True
    assert hit, 'conclusion anchor missing'
    doc.save(str(DST))
    print('saved', DST)


if __name__ == '__main__':
    main()
