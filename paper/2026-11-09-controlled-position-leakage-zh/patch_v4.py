"""Build 论文初稿_v4.docx from v3 with the review fixes and the 012/013 results."""
import copy
from pathlib import Path
from docx import Document
from docx.shared import Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH

SRC = Path('论文初稿_v3.docx'); DST = Path('论文初稿_v4.docx')
FIG = Path('audit012/fig0-corrected.png')

TITLE = '室内家具位置泄露：行走覆盖、分散交互与传感器误差的三层测量'
SUBTITLE = '受控万房 10,000 间 · 冻结双设备 64 条长记录 · 真实单房 n=1'

REPL = [
    ('不增加任何活动量', '行走路线与访次保持相同'),
    ('这条预算不是常数：加入声明的桌近墙先验后升至82.6%，更换有限解码器后升至94.5%，因此“活动够了”只能与侧信息和估计器一并报告。',
     '这条预算不是常数：在同一1,000间开发房上加入声明的桌近墙先验，整屋全中由65.1%升至82.6%；在另1,000间新种子上更换有限解码器，由85.1%升至94.5%。因此“活动够了”只能与侧信息和估计器一并报告。'),
    ('同生成族的原始双设备只取得17/32的整屋全中，把前端换成真值位姿、动作仍用预测结果则为26/32，两者之差即当前传感与后端尚未消除的损失；',
     '同生成族的原始双设备在32条长记录上只取得17/32的整屋全中，把前端换成真值位姿、动作仍用预测结果则为26/32；在另外两批各32条未参与选择的记录上，冻结链分别为21/32与20/32，加入声明的储物近墙先验后提高到23/32与22/32（合并64条：64.06%对70.31%，精确McNemar p=0.289）。按严重度放大手端误差后，整条链的瓶颈先出现在前端对初始静止段的判定上：严重度1时12间只剩1间可行，严重度2及以上全部在前端失败；'),
    ('第一次有了可复算的刻度', '有了可复算的刻度'),
    ('几何上界与设备实际取得之间存在可测量的落差', '几何条件可恢复性与设备实际取得之间存在可测量的落差'),
    ('图0 三层证据链与各层干预的位置。上层，几何层在相同路线与相同14次交互下只改变接触落点，再在同一开发房上叠加声明的桌近墙先验与有限解码器；中层，设备层在相同32条冻结长记录上把前端换成真值位姿，动作仍用预测结果；下层，真实单房的原生产链复放。三层的房间集合与分母不同，纵向不可连成同一条响应曲线；横线为Wilson 95%区间，真实层n=1不给出区间，仅作存在性。',
     '图0 四组配对对比。a，同10,000间、同路线、同14次交互，只把接触从同点重复改为分散落点，39.78%对64.70%；b，同1,000间开发房，加入声明的桌近墙先验，65.1%对82.6%；c，同1,000间新种子房与相同节点上限，更换有限解码器，85.1%对94.5%；d，同32条冻结长记录、相同预测动作，只把前端位姿换成真值，53.13%对81.25%。四组的房间集合与分母不同，纵向不可连成同一条响应曲线；横线为Wilson 95%区间。真实单房不进入本图，其四件家具中心误差为0.0907、0.1079、0.1117、0.2333 m，仅作存在性。'),
    ('该区间关系是基本约束传播，不被宣称为新的可辨识理论。',
     '该区间关系是基本约束传播，不被宣称为新的可辨识理论。它同时以单实例观测已正确关联、尺寸与朝向模式已固定为条件：同类多实例（多柜、多椅）时不能把同类接触全部相交，必须先确定实例归属。'),
    ('在已知外框和家具清单尺寸的受控单间中，家具位置泄露随行走范围与交互位置多样性共同变化。等预算干预显示，分散接触比同点重复提供了更强的位置约束；墙先验与候选选择又会移动经验预算边界。原始手机和手表链路能够取得其中一部分证据，但长记录的整屋恢复仍受空间误差与有限解码损失限制。评价这种风险需要把几何可恢复性、设备取得证据的能力和真实案例分别报告；当前结果尚不支持原始双IMU达到某个统一活动阈值后即可稳定恢复完整布局。',
     '在已知外框和家具清单尺寸的受控单间中，家具位置泄露随行走范围与交互位置多样性共同变化：同路线、同访次下只把接触从同点重复改为分散落点，整屋全中率由39.78%升至64.70%，沿此预算继续增加访次则收益迅速转平。经验预算边界随声明的先验与有限解码器移动，在同一批房间上分别为82.6%与94.5%，因此“活动够了”只能与侧信息和估计器一并报告。原始手机和手表链路能取得其中一部分证据：32条冻结长记录的整屋全中为17/32，把前端换成真值位姿为26/32；另两批各32条记录上冻结链为21/32与20/32，加入声明的储物近墙先验后提高到23/32与22/32，合并64条为64.06%对70.31%，配对检验未达显著。把同一先验用于候选池过滤时两批都不增反降，说明几何先验应作用于轨迹而不是候选集。传感器误差轴进一步显示，整条链的瓶颈首先出现在前端对初始静止段的判定上。因此评价这类风险需要把几何可恢复性、设备取得证据的能力、先验的施加位置和真实案例分别报告；当前结果尚不支持原始双IMU达到某个统一活动阈值后即可稳定恢复完整布局。'),
    ('本层使用32条冻结长记录（编号11100至11131），它们未参与任何模型选择与超参数选择；',
     '本层使用32条冻结长记录（编号11100至11131），它们由生成器独立产生、未参与任何模型选择与超参数选择；'),
]

NEW_SECTIONS = [
    ('Heading 2', '4.4 两次同向复现与一次失败的先验'),
    ('Body Text', '表3的四臂只覆盖编号11100至11131的32条记录。为检查腕部与储物先验是否只是这一批的性质，本文另生成两批各32条长记录：11200至11231沿用012已冻结的生成参数，11300至11331使用未参与任何选择的新种子，两批都在冻结链上跑完同一组四臂。结果是两批的同一件事各得+6.25个百分点：11200批由21/32升至23/32（配对2对0，p=0.5），11300批由20/32升至22/32（配对4对2，p=0.6875），合并64条为41/64对45/64，精确McNemar p=0.289。方向一致且两次同向，但在64条上仍未达显著，因此本文只主张“储物近墙侧信息沿着可复现的方向改善原始输入整屋率”，不主张已确认的效应量。'),
    ('Body Text', '同一组实验里还存在一个可报告的负结果。既然桌、床、储物在生成族中总是贴墙（桌最大间隙0.150 m、床0.100 m、储物0.159 m，椅最小0.497 m），最直接的做法是把墙隙当作候选池的硬过滤。把这一过滤单独加在冻结链上，两批分别得到22/32与19/32，低于不加过滤的21/32与20/32；与储物轨迹修复叠加后为22/32与21/32，也低于只用轨迹修复的23/32与22/32。原因是间隙在预测坐标系中测量：约0.2 m的位姿误差足以把一个本来正确的框推出0.16 m窗，过滤于是删掉接近正确的候选，只留下贴墙但错位的解。这与SUMMON报告的“可行但错误”属于同一类失败，也说明声明的几何先验应作用于轨迹而不是候选集。'),
    ('Heading 2', '4.5 传感器误差把边界画在前端'),
    ('Body Text', '冻结链此前只承受生成器自带的常值偏置与白噪。为回答“换成真实手端会怎样”，本文在信号上叠加四项MEMS式误差并只移动一个严重度旋钮：缓慢游走偏置、额外白噪、标度与轴失准、时间戳抖动。同一12间房、同一解码器的结果是：严重度1时整屋只剩1/12，2与4时全部失败，且失败全部发生在前端，抛出“初始静止段不足”的异常。逐项归因显示，游走偏置与额外白噪各自就能让前端判定失效，标度误差单独作用时前端仍能通过、失败转为解码冲突，2 ms时间戳抖动单独作用则两间房都整屋命中。这条结果不改变前三层的数字，但它限定了引用范围：层二与层三的成绩是在接近生成器噪声水平的条件下取得的，真实手端的标定误差必须先跨过前端这一关。'),
]


def set_text(p, text):
    runs = p.runs
    if not runs:
        p.add_run(text); return
    runs[0].text = text
    for r in runs[1:]:
        r.text = ''


def replace_everywhere(doc, old, new):
    # Paragraph.text also concatenates hyperlink runs; writing it back would
    # duplicate the hyperlink text as a plain run, so build from p.runs only.
    hit = 0
    for p in doc.paragraphs:
        text = ''.join(r.text for r in p.runs)
        if old in text:
            set_text(p, text.replace(old, new)); hit += 1
    return hit


def insert_after(p, style, text):
    new = copy.deepcopy(p._p)
    p._p.addnext(new)
    from docx.text.paragraph import Paragraph
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
    ps = doc.paragraphs
    set_text(ps[0], TITLE)
    set_text(ps[1], SUBTITLE)
    counts = {}
    for old, new in REPL:
        counts[old[:12]] = replace_everywhere(doc, old, new)
    # swap the figure image
    target = next(p for p in doc.paragraphs if p.text.strip().startswith('图0'))
    image_par = target._p.getprevious()
    from docx.text.paragraph import Paragraph
    ip = Paragraph(image_par, target._parent)
    for r in list(ip.runs):
        if r._element.findall('.//{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}inline'):
            r._element.getparent().remove(r._element)
    ip.add_run().add_picture(str(FIG), width=Cm(16.4))
    ip.alignment = WD_ALIGN_PARAGRAPH.CENTER
    # new subsections before section 5
    anchor = next(p for p in doc.paragraphs if p.text.strip().startswith('5 第三层结果'))
    prev = anchor._p.getprevious()
    from docx.text.paragraph import Paragraph as P2
    cursor = P2(prev, anchor._parent)
    for style, text in NEW_SECTIONS:
        cursor = insert_after(cursor, style, text)
    doc.save(str(DST))
    print('saved', DST, counts)


if __name__ == '__main__':
    main()
