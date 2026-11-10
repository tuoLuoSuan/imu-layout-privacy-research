"""Chinese v21 -> v22: placement transfer, declared-prior ceiling, abstract update."""
import glob, os
from copy import deepcopy
from docx import Document
from docx.text.paragraph import Paragraph

ROOT = r"D:/Project/imu环境重建/paper/2026-11-09-controlled-position-leakage-zh"
SRC = sorted(glob.glob(os.path.join(ROOT, "论文初稿_v21_031.docx")))[0]
DST = os.path.join(ROOT, "论文初稿_v22.docx")

P1 = ("落点效应在设备链上也能复现。同一间房、同一条路线、同样14次接触、同样的手机与手表种子、"
      "同样的前端、接触回访、储物墙距修复与解码器，只改接触落在哪个面。开发用的12间给出"
      "分散7/12（F1 0.8135）与重复8/12（0.8379），差−8.33个百分点，精确McNemar p=1.0；"
      "这个规模分辨不出几何层那么大的效应。另换64间此前没在任何一臂里用过的房，"
      "分散48/64（75.0%，F1 0.9304）、重复30/64（46.9%，0.8354）；"
      "20间只在分散下整屋全中、2间只在重复下全中，配对差28.12个百分点，"
      "房间bootstrap 95% [15.62, 40.62]，精确McNemar p=1.2e-4。合并76间是55对38，"
      "+22.37个百分点 [10.53, 34.21]，p=9.1e-4。方向与量级都和几何层一致，12间那一档是欠功效，"
      "不是反例。两条设备批次共用同一条链，所以这个估计只对这条链的采集与精修成立，"
      "不能外推到别的解码器。")

P2 = ("只用声明先验时，换一个估计器结果也差不多。按声明的件数、尺寸、互不重叠、贴墙与支撑关系，"
      "每间房独立抽2,000份布局，全部过同一套校验，同样32间上F1 0.0878，"
      "64,000份里只4份整屋全中——所以这不是某个解码器的毛病。"
      "用真值挑出每间最好的那一份，F1 0.7371、4/32整屋全中；这个上界还随件数塌："
      "4件0.950（4/5间）、5件0.725（0/13）、6件0.716（0/14）、7件0.595（0/12），"
      "五件以上78,000份没有一份整屋全中。这一族先验最多给到近似摆位，整屋全中要靠惯性证据补——"
      "同样32间上惯性链是0.8013、21/32。这个上界属于一个采样族，不等于所有只用先验的推断。")

ABS_ADD = ("落点效应在端到端设备链上同样出现：64间新房分散48/64对重复30/64，+28.12个百分点，"
           "精确McNemar p=1.2e-4；只用声明先验时，独立采样64,000份布局的F1上界是0.088，"
           "用真值挑最优也只有0.737。")


def insert_after(par, body):
    el = deepcopy(par._p)
    par._p.addnext(el)
    new = Paragraph(el, par._parent)
    for r in list(new.runs)[1:]:
        r._r.getparent().remove(r._r)
    new.runs[0].text = body
    return new


def main():
    doc = Document(SRC)
    ps = doc.paragraphs
    assert ps[113].text.startswith("在20访次录音内部"), ps[113].text[:40]
    assert ps[117].text.startswith("先验对照的第二个独立批次"), ps[117].text[:40]
    p113, p117 = ps[113], ps[117]

    insert_after(p117, P2)
    insert_after(p113, P1)

    abs_p = ps[4]
    assert abs_p.text.startswith("本文测量在已知房间外框"), abs_p.text[:30]
    run = abs_p.add_run(ABS_ADD)
    if abs_p.runs and len(abs_p.runs) > 1:
        run.font.size = abs_p.runs[0].font.size
        run.font.name = abs_p.runs[0].font.name

    doc.save(DST)
    print("saved", os.path.basename(DST), "paras", len(Document(DST).paragraphs))


main()
