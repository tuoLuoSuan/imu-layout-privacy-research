const names={none:'无噪声参照',common:'共同平移 · 不变性控制',brownian:'随机游走',iid:'独立误差'};
const colors={none:'#526A7B',common:'#8B9AA5',brownian:'#3974D8',iid:'#AD764D'};
const cohorts=[['all','全部600套'],['singleton','421套单例'],['alias','179套同形房'],['dorm','宿舍'],['apartment','公寓'],['conference','会议室'],['office','办公室'],['classroom','教室'],['hotel','酒店']];
const pct=x=>(100*x).toFixed(2)+'%';
export function evidenceRows(data,cohort,visits,sigma){
  return ['none','common','brownian','iid'].map(structure=>{
    const row=data.rows.find(r=>r.cohort===cohort&&r.visits===Number(visits)&&r.structure===structure&&r.sigma===(structure==='none'?0:Number(sigma)));
    if(!row)throw Error('该条件没有冻结结果');
    return row;
  });
}
export function evidenceCsv(rows){
  const heads=['cohort','visits','sigma','structure','top1_numerator','queries','top1','ci_low','ci_high','top5_numerator','top5','answered','answer_rate','mean_distance_distortion_rms_m','mean_unique_sites','ranking_scores_recomputed','invariance_control','normal_function_utility_measured'];
  return [heads,...rows.map(r=>[r.cohort,r.visits,r.sigma,r.structure,r.top1.rate.numerator,r.queries,r.top1.rate.value,...r.top1.house_bootstrap95,r.top5.rate.numerator,r.top5.rate.value,r.answer_rate.numerator,r.answer_rate.value,r.distance_distortion_rms_m_mean.value,r.observed_unique_sites_mean.value,false,r.invariant_control,false])].map(x=>x.join(',')).join('\r\n');
}
export function evidenceSvg(data,cohort='all',visits=32,sigma=.5){
  const x=n=>64+(n-8)*616/24,y=p=>245-p*205;
  let p=[];
  for(const tick of [0,.25,.5,.75,1])p.push(`<path d="M64,${y(tick)}H680" stroke="#E0E8EF"/><text x="54" y="${y(tick)+4}" text-anchor="end" fill="#647B8B" font-size="11">${tick*100}%</text>`);
  for(const v of [8,16,32])p.push(`<text x="${x(v)}" y="266" text-anchor="middle" font-size="12" fill="#375367">${v}访</text>`);
  ['none','common','brownian','iid'].forEach((s,i)=>{
    const rows=[8,16,32].map(v=>evidenceRows(data,cohort,v,sigma).find(r=>r.structure===s));
    p.push(`<polyline points="${rows.map(r=>`${x(r.visits)},${y(r.top1.rate.value)}`).join(' ')}" fill="none" stroke="${colors[s]}" stroke-width="${s==='common'?1.5:2.5}" ${s==='common'?'stroke-dasharray="4 5"':''}/>`);
    for(const r of rows){
      const active=r.visits===Number(visits),xx=x(r.visits),yy=y(r.top1.rate.value);
      if(active){const [lo,hi]=r.top1.house_bootstrap95;p.push(`<path d="M${xx},${y(lo)}V${y(hi)}M${xx-4},${y(lo)}H${xx+4}M${xx-4},${y(hi)}H${xx+4}" stroke="${colors[s]}"/>`);}
      p.push(`<circle cx="${xx}" cy="${yy}" r="${active?5:3}" fill="${s==='common'?'white':colors[s]}" stroke="${colors[s]}"><title>${names[s]} · ${r.visits}访 · top-1 ${pct(r.top1.rate.value)}</title></circle>`);
    }
    const lx=64+i*170;
    p.push(`<path d="M${lx},292h16" stroke="${colors[s]}" stroke-width="2" ${s==='common'?'stroke-dasharray="3 3"':''}/><text x="${lx+21}" y="296" font-size="10" fill="#375367">${names[s]}</text>`);
  });
  p.push(`<text x="64" y="20" fill="#173B4A" font-size="13">${cohorts.find(x=>x[0]===cohort)?.[1]||cohort} · 候选身份top-1 · 三种访问预算</text>`);
  p.push(`<text x="64" y="322" fill="#647B8B" font-size="10">正确分组 · λ=0 · 闭600候选 · σ=${sigma}m为模型参数 · common与无噪声重合</text>`);
  p.push('<text x="64" y="340" fill="#647B8B" font-size="10">冻结逐查询分数汇总，未重算匹配分数；选中点为整房点态95%区间。</text>');
  p.push('<text x="64" y="360" fill="#647B8B" font-size="10">固定攻击的条件结果；全600候选均匀猜测地板1/600=0.17%，不代表最优攻击者上界。</text>');
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 760 374" role="img" aria-label="冻结结果：访问预算与坐标误差结构的条件对照" style="font-family:Microsoft YaHei,Arial,sans-serif"><rect width="760" height="374" fill="white"/>${p.join('')}</svg>`;
}
function save(name,text,type){const u=URL.createObjectURL(new Blob([text],{type})),a=document.createElement('a');a.href=u;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);}
export async function initDefence(root){
  const response=await fetch('./research/defence-evidence.json');
  if(!response.ok)throw Error('完整条件表不可用');
  const data=await response.json();
  if(data.schema!=='defence-evidence-v1')throw Error('防护条件数据规格不匹配');
  root.innerHTML=`<div class="lab-section-head"><div><span class="lab-kicker">FULL CONDITIONS / 不只展示一个误差档</span><h3>信息暴露少一些，匹配会怎样？</h3></div><span class="lab-tag">39条件 × 9队列</span></div>
    <p>数值来自冻结产物，此处不重算匹配分数。本轮从保存的逐查询分数复核汇总与区间，不新增独立样本。</p>
    <div class="lab-controls"><label>队列 <select id="def-cohort" aria-label="防护结果队列">${cohorts.map(([v,n])=>`<option value="${v}">${n}</option>`).join('')}</select></label><label>访问预算 <select id="def-visits" aria-label="防护访问预算">${[8,16,32].map(v=>`<option value="${v}" ${v===32?'selected':''}>${v}访</option>`).join('')}</select></label><label>模型误差档 <select id="def-sigma" aria-label="防护模型误差档">${[.3,.5,1,1.5].map(v=>`<option value="${v}" ${v===.5?'selected':''}>${v} m</option>`).join('')}</select></label></div>
    <div id="def-chart" class="lab-condition-chart"></div><div id="def-table"></div>
    <p class="lab-footnote">σ不是一根物理稳健性轴。Brownian定义固定为σ·累计扰动/√32，8/16访沿用同一分母；各条件是相同房屋的配对情景。共同平移是数学不变性检查，原评分程序直接复用无噪声分数，不作第二条独立证据。</p>
    <p class="lab-footnote">队列仅用于分层评价，不向攻击者提供房型或同形标签；候选仍为600。固定攻击分数低于均匀猜测地板1/600=0.17%时，不能声称理性攻击者也低于该地板。“间距失真”是对应站点对距离误差的查询级RMS均值，仅是几何代理，未测正常动作识别、导航或能耗。区间按本队列房型配额分层整房抽样，保留每房四路线；是点态区间，不作多重比较显著性判断。更换评分器验证：未完成；分组器族防护验证：未完成。</p>
    <div class="lab-downloads"><button id="def-csv" type="button">当前防护条件 CSV ↓</button><button id="def-svg" type="button">访问预算对照 SVG ↓</button><a href="research/defence-evidence.json" download>完整351行与来源 JSON ↓</a></div>`;
  const q=id=>root.querySelector('#'+id),settings=()=>[q('def-cohort').value,Number(q('def-visits').value),Number(q('def-sigma').value)];
  function render(){
    const [cohort,visits,sigma]=settings(),rows=evidenceRows(data,cohort,visits,sigma);
    q('def-chart').innerHTML=evidenceSvg(data,cohort,visits,sigma);
    q('def-table').innerHTML=`<div class="lab-table-wrap"><table class="lab-table"><thead><tr>${['坐标输入条件','身份top-1 / 全部','整房95%区间','top-5 / 全部','作答率','平均已访站点数','间距失真RMS'].map(x=>`<th>${x}</th>`).join('')}</tr></thead><tbody>${rows.map(r=>`<tr><td>${names[r.structure]}</td><td>${pct(r.top1.rate.value)}</td><td>${r.top1.house_bootstrap95.map(pct).join(' – ')}</td><td>${pct(r.top5.rate.value)}</td><td>${r.queries}/${r.queries} · 100%</td><td>${r.observed_unique_sites_mean.value.toFixed(2)}</td><td>${r.distance_distortion_rms_m_mean.value.toFixed(3)} m</td></tr>`).join('')}</tbody></table></div>`;
  }
  for(const id of ['def-cohort','def-visits','def-sigma'])q(id).addEventListener('change',render);
  q('def-csv').addEventListener('click',()=>{const s=settings();save(`defence-${s.join('-')}.csv`,'\uFEFF'+evidenceCsv(evidenceRows(data,...s)),'text/csv;charset=utf-8');});
  q('def-svg').addEventListener('click',()=>{const s=settings();save(`defence-budget-${s[0]}-${s[2]}.svg`,evidenceSvg(data,...s),'image/svg+xml');});
  render();
}
