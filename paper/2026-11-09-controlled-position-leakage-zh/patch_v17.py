
from pathlib import Path
from docx import Document
from docx.shared import Cm

HERE = Path(r'D:/Project/imu环境重建/paper/2026-11-09-controlled-position-leakage-zh')
SRC = HERE / '论文初稿_v16.docx'
DST = HERE / '论文初稿_v17.docx'
FIG = HERE / 'figures/cvpr/fig3_budget_quality023.png'

doc = Document(str(SRC))


def set_text(p, text):
    for r in list(p.runs):
        r._element.getparent().remove(r._element)
    p.add_run(text)


paras = doc.paragraphs
idx = {p.text[:12]: i for i, p in enumerate(paras)}

# ---------- abstract: one clause on the interaction ----------
abs_p = paras[4]
anchor = '门控跟踪在不动无扰动档的前提下取回5/12。'
assert anchor in abs_p.text
new_abs = abs_p.text.replace(anchor, anchor + '把访次与误差放在同一批12间上，两者相互纠缠：传感较好时增加访次有小幅增益（严重度0时6次到14次由18/36升到23/36），严重度1时反而下降（14/36降到11/36）；同一严重度0到1的代价随记录变长放大，6次访次只丢1.3间，14次丢4.0间（Wilcoxon p=0.0156）。')
set_text(abs_p, new_abs)

p109 = paras[109]
p110 = paras[110]
assert p109.text.startswith('九格的整屋全中')
assert p110.text.startswith('改用前缀一致协议后')

new109 = ('本节把网格改成三次独立实现。同一批12间（11500至11511）、同一组访次6、10、14与严重度0、0.5、1，每格独立抽取三次噪声，'
          '每格因此有36次观测；路线、前端、精修与解码器都不变，同一次实现内三个访次共享噪声前缀。九格的整屋全中（36次中命中几次，'
          '括注为折算到12间的房间数）是18（6.0）、16（5.3）、14（4.7）与21（7.0）、20（6.7）、12（4.0）与23（7.7）、21（7.0）、11（3.7）。'
          '实例位置F1的格均值从14次访次、严重度0的0.896降到14次访次、严重度1的0.402。')
set_text(p109, new109)

new110 = ('两条轴因此不再各自给方向，而是一个交互。严重度从0提到1：6次访次丢1.3间，10次丢3.0间，14次丢4.0间；14次那一档7间变差、'
          '0间变好、5间持平，按每间房在三次实现中的命中数（0至3）做Wilcoxon符号秩，p=0.0156（10次p=0.0625，6次p=0.4375）。'
          '把访次从6提到14：严重度0时多1.7间（p=0.25），严重度0.5时多1.7间（p=0.1875），严重度1时反而少1.0间（p=0.50）。'
          '机制是记录长度：每加一次访次，同一段步行变长，慢变偏置积分更久，对整屋的伤害更大。所以“需要多少活动”不能脱离记录长度与'
          '误差水平单独讲；本节支持一个交互，不支持设备层的活动阈值。')
set_text(p110, new110)

from copy import deepcopy
from docx.text.paragraph import Paragraph
extra_el = deepcopy(p110._p)
p110._p.addnext(extra_el)
extra = Paragraph(extra_el, p110._parent)
set_text(extra, '旧协议的单次实现为什么会给出另一个角。原手机生成器按记录顺序从同一条随机流取加速度与陀螺噪声，扰动模型又按整段记录'
                '消耗随机数并把偏置游走对全记录均值中心化，于是同一种子的不同时长记录在开头就拿到不同的噪声；给两者加显式选项'
                '（分通道随机流、偏置以首样本为参照）后，同一间房6、10、14次记录的加速度、陀螺与时间戳前缀逐位相同。'
                '改用该协议后108格里有33格命中状态改变，无扰动档36格中改了8格。此前报告的7/6/3、7/6/6、8/7/4是单次实现加旧协议的结果，'
                '其中4/12那一格在三次实现下落3.7/12，邻格次序也一并改变；本稿因此只报告三次实现的均值与按房间计数的检验，'
                '不从单次实现读轴的符号。此前“新增重复接触只会把等价类做大”的表述撤回——在固定假设空间与固定容差下增加一条一致证据'
                '只会让可行集变小或不变，F1的下降更可能来自记录时长、噪声实现、轨迹估计与候选截断的共同作用。')

# ---------- figure 9 ----------
cap_idx = next(i for i, p in enumerate(doc.paragraphs) if p.text.startswith('图9'))
fig_p = doc.paragraphs[cap_idx - 1]
assert 'blip' in fig_p._p.xml
for r in list(fig_p.runs):
    r._element.getparent().remove(r._element)
fig_p.add_run().add_picture(str(FIG), width=Cm(18.3))

cap_p = doc.paragraphs[cap_idx]
set_text(cap_p, '图9 活动访次与传感严重度的九格实测结果。格内数值是三次独立噪声实现的均值（每格36次观测，单位为12间中的命中房间数）；'
                '访次在传感较好时带来增益，在严重度1时反转为损失，两条轴因此不可分离。检验按每间房的0至3次命中做Wilcoxon符号秩。')

doc.save(str(DST))
print('saved', DST)
