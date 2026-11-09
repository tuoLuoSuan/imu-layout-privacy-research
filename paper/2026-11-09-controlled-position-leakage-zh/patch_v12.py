
import re
from pathlib import Path
from docx import Document
from docx.shared import Inches, Pt
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import docx.opc.constants as C

HERE = Path(__file__).resolve().parent
SRC, DST = HERE/'论文初稿_v11.docx', HERE/'论文初稿_v12.docx'
FIG = HERE/'figures/cvpr'

doc = Document(SRC)
paras = doc.paragraphs

def replace_in_runs(p, old, new):
    hit = 0
    for r in p.runs:
        if old in r.text:
            r.text = r.text.replace(old, new); hit += 1
    return hit

def set_text(p, text):
    for child in list(p._p):
        if child.tag == qn('w:r') or child.tag == qn('w:hyperlink'):
            p._p.remove(child)
    p.add_run(text)

def add_link(p, url, text):
    rid = p.part.relate_to(url, C.RELATIONSHIP_TYPE.HYPERLINK, is_external=True)
    hl = OxmlElement('w:hyperlink'); hl.set(qn('r:id'), rid)
    r = OxmlElement('w:r'); rPr = OxmlElement('w:rPr')
    c = OxmlElement('w:color'); c.set(qn('w:val'), '1F4E79'); rPr.append(c)
    u = OxmlElement('w:u'); u.set(qn('w:val'), 'single'); rPr.append(u)
    r.append(rPr)
    t = OxmlElement('w:t'); t.text = text; r.append(t)
    hl.append(r); p._p.append(hl)

# 1 renumber before inserting new captions
n5 = sum(replace_in_runs(p, '图5', '图9') for p in paras)
n4 = sum(replace_in_runs(p, '图4', '图8') for p in paras)
print('renumber hits', n5, n4)

ABS = ('惯性记录能泄露多少室内家具布局，取决于分析者能取得多少空间上分散的接触，而不只取决于记录多长。'
'要让这句话可测，本文把证据分成三层，三层共用一条冻结链路。第一层用理想轨迹与类别接触坐标，在10,000间受控单间、55,000件目标家具上测量行走覆盖与接触落点的响应；'
'第二层把手机六轴与手表三轴的原始信号送入冻结链路，在32条未参与模型选择的长记录上干预轨迹前端、腕部通道与时钟对应；第三层把一间2.84×4.045 m宿舍的原生产链复放一遍。'
'\n'
'在相同路线与相同14次交互下，只把接触从同点重复改为分散落点，整屋全中率由39.78%升到64.70%（配对增益24.92个百分点，95%区间24.00至25.84）；沿这个预算继续加访次，收益很快转平。'
'预算也不是房间的固有属性：同一批1,000间开发房加入声明的桌近墙先验后，整屋全中由65.1%升到82.6%；另1,000间新种子房换一个有限解码器，由85.1%升到94.5%。'
'只报告需要多少活动而不报告先验与估计器，这个数字没有意义。'
'\n'
'设备一侧的落差同样可测。同生成族的原始双设备记录在32条长记录上只取得17/32的整屋全中；把前端换成真值位姿、动作仍用预测结果，则是26/32。'
'另外两批各32条未参与选择的记录上，冻结链是21/32与20/32，加入声明的储物近墙先验后为23/32与22/32（合并64条：64.06%对70.31%，精确McNemar p=0.289）。'
'\n'
'余量小得惊人。加速度均方根差只到0.013 m/s²（约1.3 mg）时，12间的整屋全中已由7间降到3间；严重度1只剩1间，2及以上全部在前端对初始静止段的判定上失败。'
'在该前端加一层门控的陀螺零偏跟踪，0.5档由12/32回到18/32，1档由3/32回到14/32，无扰动档不触发修正（24/32不变），另一批32间上复现后合并64间为25/64到34/64（p=0.0225）。'
'把均方根固定、只换时间结构，慢变陀螺误差让12间全部失去整屋命中，同样幅度的慢变加速度误差仍有8/12；门控跟踪在不动无扰动档的前提下取回5/12。'
'真实单房四件家具的中心误差为0.09至0.23 m，这是存在性案例，不是跨域验证。'
'\n代码仓库：')
set_text(paras[4], ABS)
add_link(paras[4], 'https://github.com/tuoLuoSuan/imu-layout-privacy-research',
         'https://github.com/tuoLuoSuan/imu-layout-privacy-research')

P1 = ('在室内导航、活动识别和健康监测里，惯性测量单元通常被当作描述使用者运动的传感器。运动还受环境约束：通道引导行走，坐下暴露座椅附近的位置，拉开柜门要站在特定操作面前。'
'不采集图像，这些约束照样能把局部动作变成家具位置线索。由此得到的隐私问题是定量的：一个已经拿到运动数据的分析者，要看多大范围、多少种空间上不同的交互，才能定位室内家具？')
P2 = ('从运动恢复环境已有可行路线。Walk2Map用学习到的轨迹与平面图关系预测房间边界、门和家具区域；CoGuide把轨迹到布局的恢复写成空间逆问题，在对比表示上引导扩散生成。'
'SUMMON从人体接触预测出发，用物理约束合成被交互过的物体；IMU4D用可穿戴惯性数据估计人体运动与粗粒度场景结构。'
'这些工作给出的是不同形式的恢复或生成能力，没有回答另一个问题：这点信息究竟来自哪一次走动、哪一次接触。')
P3 = ('位置相关动作也能辅助惯性定位。ActionSLAM把坐椅、开门当作地标来约束漂移，RoNIN研究真实携带条件下的神经惯性导航。'
'所以重复交互用于定位、惯性轨迹用于场景推断，都不是本文的发明。缺的是可测性：既有工作报告能否恢复，很少报告需要多少活动才能恢复。'
'活动量常被压成一个标量，时长或访次，而同访次可以对应差别很大的接触空间跨度。预算结论又依赖给定的侧信息与解码器，换先验或换估计器后同一条线还在不在原位，没有系统报告。'
'几何证据充足也不等于设备拿得到它。三点合起来，使活动够了这句话在现有文献里无法被证伪。')
P4 = ('本文把三处缺口写成三个可分别干预的量，并按此组织三层证据。第一层用理想轨迹与类别接触坐标，在同路线、同访次的配对设计下只改接触落点，测几何预算的响应；'
'第二层把手机与手表原始信号送进冻结链路，同一解码器下干预轨迹前端、腕部通道与时钟对应，测设备取得几何证据时的损失；第三层保留一间真实房间的原生产链，看记录能否形成可用的二维结果。'
'由此得到三点推进：接触落点是独立于访次的可干预变量；预算点随声明的先验与有限解码器移动，必须条件化报告；几何条件可恢复性与设备实际取得之间有可测量的落差。'
'图0把六组同集合对照放在一张图上。')
for i, t in ((7, P1), (8, P2), (9, P3), (10, P4)):
    set_text(paras[i], t)

CAP0 = ('图0 六组同集合对照。前三组来自模拟层：同10,000间、同路线、同14次交互只把接触从同点重复改为分散落点，39.78%对64.70%；'
'同1,000间开发房加入声明的桌近墙先验，65.1%对82.6%；同1,000间新种子房与相同节点上限更换有限解码器，85.1%对94.5%。'
'中间两组来自原始记录：0.5档与1.0档加入门控陀螺跟踪。最后一组是诊断：同32条冻结长记录、相同预测动作，只把前端位姿换成真值，53.13%对81.25%。'
'各行的房间集合与分母互不相同，纵向不连成一条响应曲线；区间为配对比例的Newcombe混合得分区间。真实单房不进入本图，其四件家具中心误差为0.0907、0.1079、0.1117、0.2333 m，仅作存在性。')

fig_p = None
for p in paras:
    if p._p.findall('.//' + qn('a:blip')) and p.style.name == 'Captioned Figure':
        fig_p = p; break
for r in list(fig_p.runs): r._r.getparent().remove(r._r)
fig_p.add_run().add_picture(str(FIG/'fig2_paired_contrasts.png'), width=Inches(4.6))
set_text(paras[12], CAP0)

# 2 insert new figures before section headings
def heading(prefix):
    for p in doc.paragraphs:
        if p.style.name.startswith('Heading') and p.text.strip().startswith(prefix):
            return p
    raise SystemExit('heading not found: ' + prefix)

BLOCKS = [('4.9', 'fig6_qualitative_rooms.png', 5.0,
  '图4 四间房的真值与预测。虚线为真值，实线为预测；括号内数字是超过0.25 m的中心误差。四间房分别对应全对、一件偏移、两件出错，以及没有任何候选通过覆盖约束的情形。'),
 ('4.10', 'fig4_error_spectra.png', 4.6,
  '图5 同样的均方根，三种时间结构。12间房各自恢复的整屋数；竖向虚线为无扰动的冻结链。三组柱子分别是冻结前端、门控陀螺跟踪与无门控跟踪，脚注给出两条对照读数。'),
 ('4.11', 'fig5_selection_criteria.png', 4.6,
  '图6 七类选择准则在三个批次上相对基线的变化。缺标记表示该批未跑；A、B为无扰动批，C为0.5档。三条基线分别为24/32、23/32与17/32。'),
 ('5 ', 'fig3_budget_quality.png', 4.6,
  '图7 活动预算与证据质量。12间房上访次与严重度的3×3配对网格，格内为恢复间数，边注为百分点差。质量轴的总差为11对2（p=0.0225），预算轴为6对3（p=0.508）。')]
for prefix, img, w, cap in BLOCKS:
    h = heading(prefix)
    fp = doc.add_paragraph(style='Captioned Figure')
    h._p.addprevious(fp._p)
    fp.add_run().add_picture(str(FIG/img), width=Inches(w))
    cp = doc.add_paragraph(cap, style='Image Caption')
    h._p.addprevious(cp._p)

doc.save(DST)
d2 = Document(DST)
print('saved', DST.name, 'paras', len(d2.paragraphs))
print('imgs', len([p for p in d2.paragraphs if p._p.findall('.//' + qn('a:blip'))]))
for p in d2.paragraphs:
    if p.style.name in ('Image Caption',) and p.text.startswith('图'):
        print('  cap:', p.text[:26])
