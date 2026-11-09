"""Build 论文初稿_v6.docx from v5 with the prior-placement subsection (013)."""
import copy
from pathlib import Path
from docx import Document
from docx.text.paragraph import Paragraph

HERE = Path(__file__).resolve().parent
SRC = HERE / '论文初稿_v5.docx'; DST = HERE / '论文初稿_v6.docx'

HEAD = '4.6 声明先验应该作用在轨迹上，而不是候选集上'
PARAS = [
    '上面的储物修复把先验放在观测残差里。把它改放到候选集上，同一先验就会反向伤害结果：把床、桌、储物的墙隙上界做成候选池硬过滤后，'
    '同一条轨迹修复链在新32条（11200至11231）上由23间降到22间，在独立32条（11300至11331）上由22间降到21间，合计64条中45间降到43间'
    '（不一致对0比2，精确McNemar p=0.5）；退步集中在储物，40/48降到35/48，而储物真值间隙上界正是0.159 m。',
    '让解码器同时解两遍、按“配准代价加20倍违规米数”挑一个，也挑不回来：32条新记录里31次都选了过滤解。'
    '唯一一次两臂分岔的房间说明了原因——过滤解代价0.233 m、违规0 m却少一件，未过滤解代价0.247 m、违规0.144 m却全中。'
    '过滤删掉的不是残差，而是竞争者，所以只看拟合的准则无法察觉这种损害，这正是“可行但错误”在本任务里的形态。',
    '把前端换成真值位姿做诊断，同一过滤在开发8间上不但无害，反而把7/8补到8/8、F1由0.975升到1.000、储物11/12补到12/12。'
    '因此先验本身与生成族自洽，伤害来自位姿误差与先验容差同量级：轨迹修复把相对系ADE从0.403 m降到0.178 m，才让0.15至0.16 m的窗口重新可用。'
    '这条规则也是本文对012修复与本次过滤结果差异的解释：先验应当作为观测量上的残差，而不是假设空间上的删减。',
    '这一条也把两层接起来。第一层的桌近墙先验同样是候选池过滤，在1,000间理想轨迹与语义接触上把整屋从65.1%提到82.6%；'
    '第二层的同一类过滤在0.178 m位姿误差下却两批各掉1间。两者不矛盾，且伤害并不随误差单调增长：在0.403 m的未修复链上，'
    '同一过滤是41对41的平局（两批一升一降，见4.4），因为那里的失败多先发生在候选冲突上，过滤没有机会删掉正确框；'
    '最能伤到结果的区间恰恰是系统本来就接近正确的时候。因此先验的符号取决于设备取得几何证据的程度，'
    '这也是三层证据必须分开报告的直接理由。',
]


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
    anchor = next(p for p in doc.paragraphs if ''.join(r.text for r in p.runs).startswith('这条轴的作用是限定引用范围'))
    cursor = insert_after(anchor, 'Heading 2', HEAD)
    for text in PARAS:
        cursor = insert_after(cursor, 'Body Text', text)
    tail = next(p for p in doc.paragraphs if ''.join(r.text for r in p.runs).startswith('这条轴的作用是限定引用范围'))
    doc.save(str(DST))
    print('saved', DST, 'styles', anchor.style.name, tail.style.name)


if __name__ == '__main__':
    main()
