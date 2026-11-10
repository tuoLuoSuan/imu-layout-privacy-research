"""v24: decoder and sensor-error robustness plus the budget curve (Chinese)."""
import copy
import glob
import os
import shutil

import docx
from docx.text.paragraph import Paragraph

SRC = sorted(glob.glob('*v23.docx'))[-1]
DST = '论文初稿_v24.docx'

P1 = ("落点效应不依赖某一种解码方式。同一批房、同一段录音、同一套前端与精修器，只换解码器："
      "候选上限 128 时分散 48/64 对重复 30/64（+28.12 个百分点，p=1.2e-4）；上限 64 时 52/64 对 35/64"
      "（+26.56，p=7.6e-5）；在上限 64 之上再加墙面支撑代价重排，是 54/64 对 44/64（+15.62，p=0.013）。"
      "三个解码器上符号都在，量级会变——代价重排把重复那一臂从 30 抬到 44，说明候选顺序能吸收一部分"
      "原本要靠落点才能拿到的证据。传感器误差下也一样：严重度 0.5、同样 64 间，分散 36 对重复 25"
      "（+17.19，区间 [4.69, 29.69]，p=0.013），但实例 F1 基本持平（0.743 对 0.767），"
      "这一档的收益集中在成功边界附近，而不是整体精度被抬高。见图 6a 与补充表 S14、S15。")

P2 = ("预算决定这份收益还有多大。把类别配额固定、让 k 从 6 走到 14，76 间房上分散相对随机的平均 F1 优势"
      "依次是 +0.109（30 间更好、7 间更差，符号翻转 p=3.0e-5）、+0.045、+0.010、−0.017，到 k=14 两者按构造相同"
      "（55/76）。接触落在哪里是一个杠杆，但只在预算紧的时候有用：14 次接触全部保留时，选哪几个已经无从谈起，"
      "剩下的差异是这 14 次落在多少张不同的面上，那是 4.9 节的重复/分散协议在管的事。见图 6b 与补充表 S16。")

ABS = ("在另两种解码器与 0.5 档传感器误差下同一对照的符号不变（+26.56、+15.62、+17.19 个百分点）；"
       "把类别配额固定后，分散相对随机的优势从 6 次接触的 +0.109 递减到 14 次的 0。")


def set_text(par, text):
    for run in list(par.runs)[1:]:
        run._element.getparent().remove(run._element)
    if par.runs:
        par.runs[0].text = text
    else:
        par.add_run(text)


def insert_after(anchor, text):
    el = copy.deepcopy(anchor._p)
    anchor._p.addnext(el)
    par = Paragraph(el, anchor._parent)
    set_text(par, text)
    return par


def main():
    d = docx.Document(SRC)
    ps = d.paragraphs
    anchor = None
    for p in ps:
        if p.text.strip().startswith('落点效应在设备链上'):
            anchor = p
            break
    assert anchor is not None, 'anchor missing'
    first = insert_after(anchor, P1)
    insert_after(first, P2)
    abs_par = None
    for p in ps:
        if p.text.strip().startswith('本文测量在已知房间外框'):
            abs_par = p
            break
    assert abs_par is not None, 'abstract missing'
    if abs_par.runs:
        abs_par.runs[-1].text = abs_par.runs[-1].text + ABS
    else:
        abs_par.add_run(ABS)
    d.save(DST)
    print('saved', DST, os.path.getsize(DST))


if __name__ == '__main__':
    main()
