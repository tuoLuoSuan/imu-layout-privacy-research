"""Build 论文初稿_v9.docx from v8: same-RMS shape experiment (section 4.9)."""
import copy
from pathlib import Path
from docx import Document
from docx.text.paragraph import Paragraph

HERE = Path(__file__).resolve().parent
SRC = HERE / '论文初稿_v8.docx'
DST = HERE / '论文初稿_v9.docx'

ABS_OLD = '（合并64间由25/64到34/64，p=0.0225）；'
ABS_NEW = (ABS_OLD +
           '进一步的同均方根对照显示，决定成败的是误差的时间结构而非幅度：慢变陀螺误差让12间全部失去整屋命中，'
           '而同样幅度的慢变加速度误差仍有8/12；门控陀螺跟踪在不触发无扰动档的前提下把这组损失取回5/12。')

H49 = '4.9 同样的均方根，不同的时间结构'
P90 = ('4.5节与4.7节改的是幅度，这一节把幅度固定、只改时间结构。在12间无扰动记录上，三种扰动逐轴标定到同一均方根'
       '（加速度0.02 m/s²、陀螺0.003 rad/s）：白噪服从N(0,σ)，常偏置取常数±σ，慢变游走由累积和去均值后按每轴标准差重标定。'
       '三者每轴标准差相同，只有谱形不同；每个条件都重跑同一条链（位移前端、接触回访、储物墙距修复、选择式解码）。'
       '整屋全中在无扰动档是10/12，白噪陀螺11/12，常偏置陀螺8/12，慢变陀螺0/12；而同样幅度的慢变加速度仍有8/12'
       '（实例位置F1为0.9107对无扰动档的0.9742）。在同幅度下，只有陀螺通道的慢变成分能把记录从布局阶段里整体拿掉。')
P91 = ('机理不在幅度，而在门限的形态。冻结前端用0.4 s滑窗判静止，陀螺判据是窗内均方再开根小于0.009 rad/s'
       '（analysis/layout/inertial010.py:21-35），并要求首个静止段落在4 s内（同文件第56行），整条记录的陀螺偏置只在那一处估计'
       '（第57行）。滑动均方不会把慢变成分平均掉：慢变陀螺误差把开场窗口顶到0.0106至0.0136 rad/s，'
       '于是11501、11503、11507的首个可接受静止段被推到210.96、66.46、344.5 s，开场6 s的通过比例由0.777降到0，'
       '三条记录在布局之前就抛错。同一批里11500是反例：它的门限照过（0.0067），轨迹仍然坏掉（路径长度为真值的1.64倍），'
       '说明门限只是两条损伤路径之一，另一条是漂移本身。')
P92 = ('两个直觉修法都不成立。把门限改成相对分位（取该记录自身低分位的1.5倍、且不低于0.009）时，'
       '慢变陀螺记录的分位值只有0.0057 rad/s，阈值仍落在0.009，11503的首个静止段只由66.46 s挪到54.77 s。'
       '把最初2 s的均值直接当陀螺偏置扣掉更糟：11500的路径比由1.64变成14.74，另两间从抛错变成0.222与0.100的退化轨迹——'
       '慢变的初值被当成常数错误扣到了整段。')
P93 = ('有效的做法是估计而不是假设。对陀螺漂移做离线跟踪，只在漂移超过1.5倍标准误或初偏置超过0.006 rad/s时才修正，'
       '并且只动陀螺：这一门控在无扰动档不触发，整屋10/12、F1 0.9742与冻结臂逐项相同；在慢变陀螺的12间上触发'
       '（漂移估计0.0045至0.0051 rad/s，标准误0.00086至0.00087），整屋由0/12回到5/12（不一致对5比0，精确McNemar p=0.0625），'
       '12间全部重新给出轨迹，路径比中位由1.911回到1.029。作为对照，不加门控、连加速度一起重估的版本把慢变双通道提到6/12，'
       '但无扰动档由10/12掉到8/12。边界是12间、一批、且谱形加在合成生成器上：均方根相同只控制幅度，不代表物理等价，'
       '也不外推到真实器件的谱形；这一节改变的是给定证据能被取到多少，不改变4.3节与4.7节的数字。')

CONC_OLD = '放宽覆盖只能把冲突转成可行，转不成正确。'
CONC_NEW = CONC_OLD + '同样幅度、不同时间结构的对照给出另一条边界：慢变陀螺误差使12间全部失去命中，而门控陀螺跟踪在不改动无扰动档的前提下取回5/12。'


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
    abs_p = doc.paragraphs[4]
    t = abs_p.runs[0].text
    assert ABS_OLD in t, 'abstract anchor missing'
    abs_p.runs[0].text = t.replace(ABS_OLD, ABS_NEW)

    last = para(doc, '最后把4.6节那组墙隙先验换到第三处放置')
    cursor = insert_after(last, 'Heading 2', H49)
    for text in [P90, P91, P92, P93]:
        cursor = insert_after(cursor, 'Body Text', text)

    conc = para(doc, '在已知外框和家具清单尺寸的受控单间中')
    tc = conc.runs[0].text
    assert CONC_OLD in tc, 'conclusion anchor missing'
    conc.runs[0].text = tc.replace(CONC_OLD, CONC_NEW)

    doc.save(str(DST))
    print('saved', DST)


if __name__ == '__main__':
    main()
