export function parseCsv(text){
  const lines=text.replace(/^\uFEFF/,'').trim().split(/\r?\n/).filter(x=>x.trim());
  const header=lines.shift()?.split(',').map(x=>x.trim().replace(/^"|"$/g,''))||[];
  const keys=['callback_elapsed_ms','x','y','z'];
  const indices=keys.map(x=>header.indexOf(x));
  if(indices.some(x=>x<0))throw Error('需要 callback_elapsed_ms、x、y、z 四列。');
  if(lines.length<2)throw Error('至少需要两条回调记录。');
  if(lines.length>100000)throw Error('本页最多查看 100000 条记录，请先分块。');
  const rows=lines.map((line,i)=>{
    const cells=line.split(',');
    const values=indices.map(k=>cells[k]?.trim().replace(/^"|"$/g,''));
    if(values.some(x=>!x||!Number.isFinite(Number(x))))throw Error(`第 ${i+2} 行数值无效，未自动补值。`);
    return values.map(Number);
  });
  if(rows.some((x,i)=>x[0]<0||(i&&x[0]<=rows[i-1][0])))throw Error('时间需要非负并逐条增加，当前记录存在倒退或重复。');
  return rows;
}
