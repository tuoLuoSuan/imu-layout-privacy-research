# -*- coding: utf-8 -*-
"""v12 -> v13: replace the budget-grid claims with the clustered and prefix-matched result."""
from pathlib import Path
import docx
HERE = Path(__file__).resolve().parent
src = HERE / "论文初稿_v12.docx"
dst = HERE / "论文初稿_v13.docx"
doc = docx.Document(str(src))
ps = doc.paragraphs

def rewrite(p, text):
    for r in p.runs[1:]:
        r.text = ""
    if p.runs:
        p.runs[0].text = text
    else:
        p.add_run(text)

P107 = ps[107]; P108 = ps[108]; P164 = ps[164]
assert P107.text.startswith("九格的整屋全中"), P107.text[:30]
assert "等价类做大" in P108.text, P108.text[:30]

p107_add = ("口径更正：九格的每个条件都在同一间房内重复，配对检验不能把36个条件对当作36间独立房。"
            "按房内平均再做12个房间的精确符号翻转，严重度0对1的轴效应是+25.0个百分点（p=0.133），"
            "访次14对6是+8.33个百分点（p=0.656），两条轴在房间聚类下都不显著。")
rewrite(P107, P107.text + p107_add)

p108_new = ("把噪声流修好之后，这条轴翻转。原手机生成器按记录顺序从同一条随机流取加速度与陀螺噪声，"
            "扰动模型又按整段记录消耗随机数并把偏置游走对全记录均值中心化，于是同一种子的不同时长记录在开头就拿到不同的噪声。"
            "给两者加显式选项（分通道随机流、偏置以首样本为参照）后，同一间房6、10、14次记录的加速度、陀螺与时间戳前缀逐位相同。"
            "用该协议重跑108格，整屋全中变成4、5、7与5、6、6与7、7、6；严重度轴变成−8.33个百分点（p=0.625），访次轴+11.11个百分点（p=0.406）。"
            "两套协议之间有33格（共108格）命中状态改变，其中无扰动档36格里改了8格。"
            "因此4.11节只报告九格本身：12间、每格一次实现，既分不开接触次数的作用，也分不开噪声实现的作用。"
            "此前“新增重复接触只会把等价类做大”的表述撤回——在固定假设空间与固定容差下增加一条一致证据只会让可行集变小或不变，"
            "F1的下降更可能来自记录时长、噪声实现、轨迹估计与候选截断的共同作用，而不是重复接触的几何冗余。")
rewrite(P108, p108_new)

old_clause = "访次由6提到14只多3间（p=0.51），严重度由0提到1少9间（p=0.0225）"
assert old_clause in P164.text, P164.text[-120:]
rewrite(P164, P164.text.replace(old_clause, "访次与严重度两条轴在房间聚类下都不显著（p=0.66与p=0.13），改用前缀一致的噪声后严重度方向还发生反转，所以本层只报告九格，不报告轴效应"))

doc.save(str(dst))
print("saved", dst.name)