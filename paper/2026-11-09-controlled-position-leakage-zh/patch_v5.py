"""Build 论文初稿_v5.docx from v4 with the paired sensor ladder."""
import copy
from pathlib import Path
from docx import Document
from docx.text.paragraph import Paragraph

SRC = Path('论文初稿_v4.docx'); DST = Path('论文初稿_v5.docx')

OLD45 = ('冻结链此前只承受生成器自带的常值偏置与白噪。为回答“换成真实手端会怎样”，本文在信号上叠加四项MEMS式误差并只移动一个严重度旋钮：'
         '缓慢游走偏置、额外白噪、标度与轴失准、时间戳抖动。同一12间房、同一解码器的结果是：严重度1时整屋只剩1/12，2与4时全部失败，'
         '且失败全部发生在前端，抛出“初始静止段不足”的异常。逐项归因显示，游走偏置与额外白噪各自就能让前端判定失效，标度误差单独作用时前端仍能通过、'
         '失败转为解码冲突，2 ms时间戳抖动单独作用则两间房都整屋命中。这条结果不改变前三层的数字，但它限定了引用范围：'
         '层二与层三的成绩是在接近生成器噪声水平的条件下取得的，真实手端的标定误差必须先跨过前端这一关。')

NEW45 = [
    '冻结链此前只承受生成器自带的常值偏置与白噪。为回答“换成真实手端会怎样”，本文在信号上叠加四项MEMS式误差并只移动一个严重度旋钮：'
    '缓慢游走偏置、额外白噪、标度与轴失准、时间戳抖动。在同一12间房、同一解码器上做配对阶梯：严重度0为整屋7/12（可行10间），'
    '0.5为3/12（可行3间，此时手端加速度均方根差仅0.013 m/s²，约1.3 mg），0.75为2/12，1为1/12，2与4在12间上全部失败且失败全部在前端，'
    '抛出“初始静止段不足”的异常。把解码器换回不含本文候选池先验的冻结路径，同样在0.5档掉到1/12，因此这一崩塌属于冻结链本身，'
    '而不是本文新增的候选池先验。',
    '机理不是噪声幅度而是慢漂移。旋转不变的漂移探针（11400与11402两间房）显示：0.5档时路程只多4%至10%，末端位移却已错到真值的1.6至1.7倍；'
    '1.0档在11402达3.3倍。游走偏置经二次积分变成慢变位姿偏差，把候选池推出接触环、或推出与房间外框相容的区域，于是表现为候选冲突或候选为空；'
    '白噪在积分中被平均掉，慢偏置不会。',
    '这条轴的作用是限定引用范围，而不是给出器件模型。无扰动条件下重复三次，两间房的六次运行结果完全一致（整屋命中、F1为1.000），'
    '说明各档差异不是运行噪声；但11400在0.5档失败、在0.75档反而命中，因此12间单次实现下只能报“某档还剩几间”，没有可外推的斜率。'
    '0.5档拆项后，偏置游走单独一项就把整屋从7/12压到3/12（与四项叠加的结果相同），标度误差单独作用为5/12；额外白噪在该档定义为0、'
    '0.25 ms时戳抖动单独作用都与基线逐房一致。2档时游走偏置与额外白噪各自即可触发前端异常，标度误差单独作用转为解码冲突，'
    '2 ms时间戳抖动单独作用则两间都整屋命中。层二与层三的成绩都在严重度0的条件下取得，'
    '真实手端的标定残差必须先跨过前端这道门，再跨过0.5档就已出现的余量问题。',
]

REPL = [
    ('**预测坐标系**', '预测坐标系'),
    ('按严重度放大手端误差后，整条链的瓶颈先出现在前端对初始静止段的判定上：严重度1时12间只剩1间可行，严重度2及以上全部在前端失败；',
     '按严重度放大手端误差后，这条链几乎没有余量：加速度均方根差只到0.013 m/s²（约1.3 mg），12间的整屋全中已由7间降到3间，严重度1时只剩1间，2及以上全部在前端对初始静止段的判定上失败；'),
    ('传感器误差轴进一步显示，整条链的瓶颈首先出现在前端对初始静止段的判定上。',
     '传感器误差轴进一步显示这条链没有余量：加速度均方根差0.013 m/s²时整屋已由7/12降到3/12，再往上瓶颈移到前端对初始静止段的判定。'),
]


def set_text(p, text):
    runs = p.runs
    if not runs:
        p.add_run(text); return
    runs[0].text = text
    for r in runs[1:]:
        r.text = ''


def replace_everywhere(doc, old, new):
    hit = 0
    for p in doc.paragraphs:
        text = ''.join(r.text for r in p.runs)
        if old in text:
            set_text(p, text.replace(old, new)); hit += 1
    return hit


def insert_after(p, style, text):
    new = copy.deepcopy(p._p)
    p._p.addnext(new)
    np_ = Paragraph(new, p._parent)
    for r in np_.runs[1:]:
        r.text = ''
    if np_.runs:
        np_.runs[0].text = text
    else:
        np_.add_run(text)
    np_.style = style
    return np_


def main():
    doc = Document(str(SRC))
    counts = {}
    for old, new in REPL:
        counts[old[:10]] = replace_everywhere(doc, old, new)
    target = next(p for p in doc.paragraphs if ''.join(r.text for r in p.runs).startswith('冻结链此前只承受'))
    set_text(target, NEW45[0])
    cursor = target
    for text in NEW45[1:]:
        cursor = insert_after(cursor, target.style, text)
    doc.save(str(DST))
    print('saved', DST, counts)


if __name__ == '__main__':
    main()
