
import glob, io
from docx import Document

src = glob.glob('*v17.docx')[0]
dst = 'paper_v18.docx'
d = Document(src)

add_1 = '三次实现只重抽手机噪声与扰动种子：手机种子按实现加不同偏移，手表种子不变，108 组房间条件的腕部流因此逐文件相同。这里的重复是手端噪声的重复，不能写成整套双设备噪声的三次独立抽取。'
add_2 = '上面两个方向各自只比较多与少，并不比较两个代价之差；把两个代价放在一起的直接交互检验（每间房的差值之差）为 −22.2 个百分点，12 间符号翻转精确双侧 p=0.125，4 间为负、8 间为零，因此这一交互只作为探索性结果报告。'

def append_after(prefix, extra):
    for p in d.paragraphs:
        if p.text.strip().startswith(prefix):
            r = p.add_run(extra)
            if p.runs and len(p.runs) > 1:
                base = p.runs[0]
                r.font.name = base.font.name
                r.font.size = base.font.size
                r.font.bold = None
            return True
    return False

ok1 = append_after('本节把网格改成三次独立实现', add_1)
ok2 = append_after('两条轴因此不再各自给方向', add_2)
d.save(dst)
io.open('C:/temp/paperv2/zh_patch.txt','w',encoding='utf-8').write('%s %s' % (ok1, ok2))
print(ok1, ok2)
