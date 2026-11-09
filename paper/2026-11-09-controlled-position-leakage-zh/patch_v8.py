"""Build 论文初稿_v8.docx from v7: 014 replication batch + §4.8 剩余损耗位置."""
import copy
from pathlib import Path
from docx import Document
from docx.text.paragraph import Paragraph

HERE = Path(__file__).resolve().parent
SRC = HERE / '论文初稿_v7.docx'
DST = HERE / '论文初稿_v8.docx'

ADD_ABS_OLD = '（24/32不变）；'
ADD_ABS_NEW = '（24/32不变），并在另一批32间上复现（合并64间由25/64到34/64，p=0.0225）；'

ADD_CONC = ('把每实例候选域限制到真值近邻后仍有4间无解，说明这条链的整屋率上限是28/32（硬覆盖与互不重叠的形式下）；'
            '放宽覆盖只能把冲突转成可行，转不成正确。')

H48 = '4.8 剩余损耗不在候选池，而在覆盖与选择'
P84 = ('为定位剩余损耗，本文用一条只读探针把联合搜索收到的候选池与真值并置，探针不参与解码。'
       '32间无扰动记录里，每一个真值实例在截断后的候选池（上限128）中都存在中心误差不超过0.5 m的候选，'
       '即提案与截断没有丢失任何实例。把每个实例的候选域限制到真值近邻、再跑同一个联合搜索，'
       '28间可行且全部实例命中；其余4间（11518、11523、11529、11531）仍报候选冲突。'
       '其中11518与11531各有2个事件没有任何近真值候选覆盖到（19个目标），11523与11529的阻塞来自近真值框之间的互不重叠约束。'
       '因此在这套“硬覆盖加互不重叠”的形式下，整屋率的可达上限是28/32，而实际解码是24/32。')
P85 = ('先尝试放宽覆盖：允许事件被丢弃并按λ计价。第一版下界把将来可能被覆盖的事件也算进剪枝，属于不可采纳的下界，'
       '结果被压到11至16间；改成只计已丢弃事件后，λ取1、3、10时都稳定在23/32：32间全部可解，整屋反而少1间（丢11502）。'
       '也就是说，把“冲突”换成“可行”并不能换成“正确”。这与SUMMON在去穿透与去接触两档上的分离同型——'
       '可行率上去了，正确率不动。')
P86 = ('再扫描候选保留上限。同一批32间，上限取32、48、64、80、96、128时整屋分别是18、23、25、24、24、24间，'
       'F1分别是0.687、0.844、0.905、0.916、0.916、0.917。截断在这里起的是正则化作用：'
       '池子太小会删掉真解，太大则让等代价的错误组合重新进入搜索。因此“提高候选覆盖率”不是免费杠杆。')
P87 = ('最后把4.6节那组墙隙先验换到第三处放置：不删候选，只在候选代价上加λ倍的违规米数。上限取64时，'
       '11500批由24/32升到27/32，翻转的三间正是探针判定的纯选择失败（11509、11511、11515），没有一间退化；'
       '但同样设置在另外三批上要么持平（11200批23/32不变），要么只多1间（11600批0.5档由17/32到18/32），'
       '单改上限在开发8间上还从8/8降到7/8。这只是调参批上的提升，跨批不一致对为3比0（精确McNemar p=0.25），'
       '不能算复现的增益。可报告的只有一条：在这些记录上，剩余损耗的位置是覆盖形式与候选选择，不是提案召回；'
       '要把它换成整屋率的提升，需要一个不依赖批内调参的选择准则。')

REPL = ('这条修复的边界同样要写清。它在另生成的32间（11600至11631，只跑0.5档）上复现：由13/32升到16/32'
        '（另一种跟踪变体为17/32），与上一批合并后是25/64到34/64（+14.06个百分点，不一致对11比2，精确McNemar p=0.0225）。'
        '它只修陀螺，加速度与活动模型未动；2档仍有31间在前端报错，说明初始静止段这一关没有跨过；'
        '严重度是合成信号上的相对刻度，不是实测器件公差；迁移到真实手端要先有可核对的时间基准与静止协议，'
        '因此它改变的是“给定几何证据能被取到多少”，而不是本文第一层与第三层的数字。')


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
    assert ADD_ABS_OLD in t, 'abstract anchor missing'
    abs_p.runs[0].text = t.replace(ADD_ABS_OLD, ADD_ABS_NEW)

    set_text(para(doc, '这条修复的边界同样要写清'), REPL)

    last = para(doc, '这条修复的边界同样要写清')
    cursor = insert_after(last, 'Heading 2', H48)
    for text in [P84, P85, P86, P87]:
        cursor = insert_after(cursor, 'Body Text', text)

    conc = para(doc, '在已知外框和家具清单尺寸的受控单间中')
    tc = conc.runs[0].text
    anchor = '无扰动档保持24/32不变，说明这一层损失来自可标定的慢变偏置而不是信息缺失。'
    assert anchor in tc, 'conclusion anchor missing: ' + tc[-120:]
    conc.runs[0].text = tc.replace(anchor, anchor + ADD_CONC)

    doc.save(str(DST))
    print('saved', DST)


if __name__ == '__main__':
    main()
