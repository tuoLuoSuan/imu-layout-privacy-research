import {initDefence} from './defence.mjs';
const esc=x=>String(x).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pct=x=>(100*x).toFixed(2)+'%';
const titles=['正确分组 · oracle','固定阈值分组','密度分组'];
const modeColors=['#526A7B','#3974D8','#AD764D'];
const pointColors=['#3974D8','#418D81','#AD764D','#8265A2','#567D9E','#9B725C','#5F8A69','#97677B'];
const kinds={bed:'床',table:'桌',chair:'椅',cabinet:'柜',sofa:'沙发',counter:'台面',shelf:'书架',sink:'水槽',toilet:'卫浴'};
export function groupView(route,mode,visits=32){
  const m=route.methods[mode],count=Math.max(1,Math.min(32,Number(visits)));
  return {shownVisits:count,totalVisits:32,inferenceScope:'full_record_offline',
    shownPoints:route.observed.slice(0,count),groups:m.representatives.map((xy,id)=>({id,xy,members:m.assignments.flatMap((x,i)=>x===id?[i]:[])})),method:m};
}
export function aggregateRows(index,cohort='all'){
  return index.modes.map((mode,i)=>{
    const r=index.aggregate_rows.find(r=>r.cohort===cohort&&r.grouping===mode);
    if(!r)throw Error('缺少该队列的冻结结果');
    return {title:titles[i],mode,color:modeColors[i],rate:r.metrics.identity_top1.rate,
      ci:r.metrics.identity_top1.house_bootstrap95,ceiling:r.complete_02m_representation_ceiling.value,
      answer:r.rank_answer_rate,retained:r.target_capacity_retained,
      precision:r.answered_identity_top1,houses:r.houses,queries:r.queries};
  });
}
export function defenceRows(index){
  return ['none','common','brownian','iid'].map(s=>index.defence.rows.find(r=>r.structure===s));
}
export function relationMatrixSvg(route,mode){
  const labels=route.methods[mode].assignments,colors={tp:'#418D81',fp:'#AD764D',fn:'#A8BED1',tn:'#EAF0F5'};let cells=[];
  for(let i=1;i<32;i++)for(let j=0;j<i;j++){
    const actual=route.site_ids[i]===route.site_ids[j],predicted=labels[i]===labels[j];
    const type=actual?(predicted?'tp':'fn'):(predicted?'fp':'tn');
    cells.push(`<rect x="${34+j*8.5}" y="${23+i*8.5}" width="8" height="8" fill="${colors[type]}"><title>访问${j+1} / ${i+1} · ${type.toUpperCase()}</title></rect>`);
  }
  for(const n of [1,8,16,24,32])cells.push(`<text x="${38+(n-1)*8.5}" y="16" font-size="10" text-anchor="middle" fill="#708595">${n}</text><text x="25" y="${30+(n-1)*8.5}" font-size="10" text-anchor="end" fill="#708595">${n}</text>`);
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 322 311" role="img" aria-label="评价侧32访496对关系，找对、误并和漏掉分别着色"><title>评价侧 · 496对访问关系</title>${cells.join('')}</svg>`;
}
function projection(points,width=600,height=420){
  const xs=points.map(p=>p[0]),ys=points.map(p=>p[1]);
  const xmin=Math.min(...xs),xmax=Math.max(...xs),ymin=Math.min(...ys),ymax=Math.max(...ys);
  const scale=Math.min((width-(width<200?18:84))/Math.max(xmax-xmin,.4),(height-(width<200?18:68))/Math.max(ymax-ymin,.4));
  return {p:([x,y])=>[width/2+(x-(xmin+xmax)/2)*scale,height/2-(y-(ymin+ymax)/2)*scale],scale};
}
export function sceneSvg(house,route,{mode=1,visits=32,kind='truth',active=visits-1}={}){
  const truth=kind==='truth',view=groupView(route,mode,visits),m=view.method;
  const extent=truth?house.rooms.flatMap(r=>[[r.rect[0],r.rect[1]],[r.rect[2],r.rect[3]]]):route.observed.concat(m.representatives);
  const {p,scale}=projection(extent);const point=xy=>p(xy).map(x=>x.toFixed(2)).join(',');
  let parts=[];
  if(truth){
    for(const room of house.rooms){const [x0,y0,x1,y1]=room.rect,[x,y]=p([x0,y1]);parts.push(`<rect x="${x}" y="${y}" width="${(x1-x0)*scale}" height="${(y1-y0)*scale}" rx="2" fill="#FAFCFE" stroke="#68818C" stroke-width="2.5"/>`);}
    for(const door of house.doors){const [x0,y0,x1,y1]=door.rect,[x,y]=p([x0,y1]);parts.push(`<rect x="${x}" y="${y}" width="${(x1-x0)*scale}" height="${(y1-y0)*scale}" fill="#FAFCFE"/><path d="M${x},${y}v${(y1-y0)*scale}M${x+(x1-x0)*scale},${y}v${(y1-y0)*scale}" stroke="#A2B7C2" stroke-width=".8"/>`);}
    for(const object of house.objects){const [x0,y0,x1,y1]=object.rect,[x,y]=p([x0,y1]);const bed=object.kind==='bed';parts.push(`<rect x="${x}" y="${y}" width="${(x1-x0)*scale}" height="${(y1-y0)*scale}" rx="2" fill="${bed?'#E3ECF4':object.kind==='cabinet'?'#DDEEE8':'#ECEFF1'}" stroke="#B0C0CA" stroke-width=".8"><title>${esc(kinds[object.kind]||object.kind)} · 合成物体</title></rect>`);if(bed){parts.push(`<path d="M${x+3},${y+(y1-y0)*scale*.25}h${Math.max(0,(x1-x0)*scale-6)}" stroke="#B6C6D1" stroke-width="1"/>`);}}
    for(const [i,path] of route.paths.slice(0,view.shownVisits).entries())parts.push(`<polyline points="${path.map(point).join(' ')}" fill="none" stroke="${i===active?'#3974D8':'#96AFC9'}" stroke-width="${i===active?2.8:1.25}" opacity="${i===active?1:.55}" stroke-linejoin="round"/>`);
    for(const site of house.sites){const [x,y]=p(site.xy);parts.push(`<circle cx="${x}" cy="${y}" r="4.5" fill="#fff" stroke="#547385" stroke-width="1.5"/><text x="${x+7}" y="${y-6}" font-size="16" fill="#516775">S${site.id}</text>`);}
    const [ex,ey]=p(house.entry);parts.push(`<path d="M${ex-5},${ey+5}l5,-9l5,9z" fill="#418D81"/><text x="${ex+9}" y="${ey+5}" font-size="10" fill="#418D81">入口</text>`);
  }else{
    for(let x=60;x<600;x+=60)parts.push(`<path d="M${x},24V393" stroke="#E5ECF2" stroke-width=".6"/>`);
    for(let y=30;y<400;y+=60)parts.push(`<path d="M24,${y}H576" stroke="#E5ECF2" stroke-width=".6"/>`);
    parts.push(`<polyline points="${view.shownPoints.map(point).join(' ')}" fill="none" stroke="#B8C6D3" stroke-width="1" stroke-dasharray="3 5"/>`);
    for(const g of view.groups){const [x,y]=p(g.xy),color=pointColors[g.id%pointColors.length];parts.push(`<circle cx="${x}" cy="${y}" r="12" fill="#fff" stroke="${color}" stroke-width="1.5" stroke-dasharray="3 3"/><text x="${x}" y="${y-16}" text-anchor="middle" font-size="15" fill="${color}">G${g.id+1}</text>`);}
    for(const [i,xy] of view.shownPoints.entries()){const [x,y]=p(xy),g=m.assignments[i],color=pointColors[g%pointColors.length];parts.push(`<circle cx="${x}" cy="${y}" r="${i===active?7:4}" fill="${color}" stroke="#fff" stroke-width="1.2"><title>访问${i+1} · G${g+1} · (${xy[0].toFixed(3)}, ${xy[1].toFixed(3)}) m</title></circle>`);}
  }
  const xy=truth?route.truth[Math.min(active,31)]:route.observed[Math.min(active,31)];
  if(xy){const [x,y]=p(xy);parts.push(`<circle cx="${x}" cy="${y}" r="14" fill="none" stroke="#173B4A" stroke-width="2"/><circle cx="${x}" cy="${y}" r="3" fill="#173B4A"/>`);}
  const scaleM=scale>=120?1:2;parts.push(`<path d="M26,394h${scaleM*scale}" stroke="#536E80" stroke-width="2"/><text x="26" y="410" font-size="10" fill="#536E80">${scaleM} m</text>`);
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 420" role="img" aria-label="${truth?'合成房间与冻结网格路线':'合成含噪坐标与完整32访离线分组'}" style="font-family:Microsoft YaHei,Arial,sans-serif"><title>${esc(house.id)} · 合成 · ${truth?'评价侧站位':'完整32访离线分组'}</title><rect width="600" height="420" fill="${truth?'#F4F7FB':'#FBFDFE'}"/>${parts.join('')}</svg>`;
}
export function chartSvg(rows){
  const x0=192,width=480,y0=65,step=67;let s=[];
  for(const tick of [0,25,50,75,100]){const x=x0+width*tick/100;s.push(`<path d="M${x},34V239" stroke="#E2EAF0"/><text x="${x}" y="260" text-anchor="middle" font-size="12" fill="#6D8091">${tick}</text>`);}
  rows.forEach((r,i)=>{const y=y0+i*step,bar=width*r.rate.value,lo=x0+width*r.ci[0],hi=x0+width*r.ci[1];s.push(`<text x="16" y="${y+7}" font-size="14" fill="#243D50">${esc(r.title)}</text><rect x="${x0}" y="${y-10}" width="${bar}" height="21" rx="2" fill="${r.color}"/><path d="M${lo},${y}H${hi}M${lo},${y-5}V${y+5}M${hi},${y-5}V${y+5}" stroke="#173B4A" stroke-width="1.5"/><text x="716" y="${y+6}" text-anchor="end" font-size="18" fill="#173B4A">${pct(r.rate.value)}</text>`);});
  const cap=x0+width*rows[0].ceiling;s.push(`<path d="M${cap},30V239" stroke="#83939F" stroke-dasharray="4 5"/><text x="${cap-5}" y="20" text-anchor="end" fill="#728391" font-size="11">全表示上界参考 ${pct(rows[0].ceiling)}</text>`);
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 760 310" role="img" aria-label="身份top-1及整房95%区间，横轴0到100百分比" style="font-family:Microsoft YaHei,Arial,sans-serif"><rect width="760" height="285" fill="white"/>${s.join('')}<text x="430" y="281" text-anchor="middle" font-size="11" fill="#6D8091">身份 top-1 / 全部查询（%）</text><text x="430" y="301" text-anchor="middle" font-size="10" fill="#6D8091">数值来自冻结产物，此处不重算。</text></svg>`;
}
function thumbnail(h){
  const r=h.rooms.flatMap(r=>[[r.rect[0],r.rect[1]],[r.rect[2],r.rect[3]]]);const {p,scale}=projection(r,160,115);
  const rect=(r,fill,stroke)=>{const [x,y]=p([r[0],r[3]]);return `<rect x="${x}" y="${y}" width="${(r[2]-r[0])*scale}" height="${(r[3]-r[1])*scale}" fill="${fill}" stroke="${stroke}" stroke-width="1"/>`;};
  return `<svg viewBox="0 0 160 115" aria-hidden="true">${h.rooms.map(r=>rect(r.rect,'#F7FAFC','#6D8594')).join('')}${h.objects.map(r=>rect(r.rect,r.kind==='bed'?'#D3E2EF':'#DAE7E2','#B8C8CF')).join('')}${h.sites.map(s=>{const [x,y]=p(s.xy);return `<circle cx="${x}" cy="${y}" r="1.6" fill="#3974D8"/>`;}).join('')}</svg>`;
}
const table=(heads,rows)=>`<div class="lab-table-wrap"><table class="lab-table"><thead><tr>${heads.map(x=>`<th>${esc(x)}</th>`).join('')}</tr></thead><tbody>${rows.map(r=>`<tr>${r.map(x=>`<td>${esc(x)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
function download(name,text,type){const url=URL.createObjectURL(new Blob([text],{type})),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
export async function initSimulation(root){
  const request=async file=>{const r=await fetch('./research/'+file);if(!r.ok)throw Error('模拟展示数据不可用');return r.json();};
  const index=await request('simulation-index.json');
  if(index.schema!=='simulation-lab-v1'||index.houses!==600)throw Error('模拟数据规格不匹配');
  root.innerHTML=`<div class="lab-intro"><div><span class="lab-kicker">SPATIAL INFERENCE LAB / 六类合成模拟</span><h2>沿着访问，<br>看空间如何被识别。</h2><p>从600套空间里选一套，跟随32次访问，观察坐标、地点分组与候选身份之间的关系。</p></div><div class="lab-stamp"><strong>600</strong><span>测试布局</span><div>6 房型 × 100 套<br>每套 4 条冻结路线</div></div></div>
  <div class="lab-sections"><a href="#lab-explorer">空间回放</a><a href="#lab-results">总体结果</a><a href="#lab-defence">攻击条件与防护</a><a href="#lab-defence-evidence">完整防护对照</a><a href="#lab-sources">数据与导出</a></div>
  <section id="lab-explorer" class="lab-explorer"><div class="lab-section-head"><div><span class="lab-kicker">EXPLORE / 固定 Brownian 误差</span><h3>同一条记录，三种地点分组。</h3></div><span class="lab-tag">合成 · 非真实宿舍</span></div>
  <div class="lab-family" role="group" aria-label="选择模拟房型">${index.families.map((f,i)=>`<button type="button" data-family="${f.id}" aria-pressed="${i===0}">${f.name}<span>100</span></button>`).join('')}</div>
  <div class="lab-controls"><label>布局编号 <select id="lab-house" aria-label="选择布局编号"></select></label><label>访问路线 <select id="lab-route" aria-label="选择访问路线">${[0,1,2,3].map(i=>`<option value="${i}">路线 ${i+1}</option>`).join('')}</select></label><button id="lab-next" type="button">下一套布局 <span>→</span></button><details class="lab-atlas"><summary>浏览本房型100套</summary><div id="lab-atlas-grid"></div><div class="lab-atlas-pages"><button id="lab-atlas-prev" type="button">上一页</button><output id="lab-atlas-page"></output><button id="lab-atlas-next" type="button">下一页</button></div></details></div>
  <div class="lab-mode" role="group" aria-label="选择分组方法">${titles.map((t,i)=>`<button type="button" data-mode="${i}" aria-pressed="${i===1}"><i style="--series:${modeColors[i]}"></i>${t}</button>`).join('')}</div>
  <div class="lab-canvases"><article><div class="lab-canvas-title"><span>评价侧 · 合成房间</span><b id="lab-truth-label"></b></div><div id="lab-truth"></div><p>家具与网格路径只供展示和评价，不传给分组器。</p></article><article><div class="lab-canvas-title"><span>推断侧 · 含噪访问坐标</span><b id="lab-group-label"></b></div><div id="lab-observed"></div><p>虚线连访问顺序，空心圈是完整记录组中心；不表示行走轨迹。</p></article></div>
  <div class="lab-playback"><button id="lab-play" type="button" aria-label="播放访问回放">▶ 回放</button><label for="lab-progress">访问</label><input id="lab-progress" type="range" min="1" max="32" value="32" aria-label="回放到第几次访问"><output id="lab-progress-value">32 / 32</output></div><p class="lab-footnote">这是完整32访的离线结果回放；滑动只改变显示进度，不重新做前缀推断。</p><div id="lab-visits" class="lab-visits" aria-label="访问序列"></div>
  <div id="lab-record" class="lab-record" aria-live="polite"></div><div id="lab-candidates" class="lab-candidates"></div><p class="lab-footnote">个案用于解释过程，总体分数见下方；默认每个房型的首个编号，未按分数挑例。</p><details class="lab-relation"><summary>查看这32次访问的同地关系</summary><div class="lab-relation-content"><div id="lab-relation-matrix"></div><div id="lab-relation-text"></div></div></details></section>
  <section id="lab-results" class="lab-results"><div class="lab-section-head"><div><span class="lab-kicker">COMPARE / 同观测 · 同候选库</span><h3>分组误差，怎样传到身份排名？</h3></div><label>查看队列 <select id="lab-cohort" aria-label="选择结果队列">${[['all','全部600套'],['singleton','421套单例'],['alias','179套同形房'],...index.families.map(f=>[f.id,f.name+' · 100套'])].map(([v,t])=>`<option value="${v}">${t}</option>`).join('')}</select></label></div><div id="lab-chart"></div><div id="lab-result-table"></div><p class="lab-footnote">数值来自冻结产物，此处不重算。区间按房型固定数量分层抽整房，四路线一起保留，条件于当前生成器。身份并列用解析期望计分，分子可为非整数。虚线是0.2m全站位表示的身份上界参考，不是任意攻击上界。</p><div class="lab-insight"><strong>误拆的代价</strong><p>真实候选可能先被“组数不得超过候选站位数”的硬容量条件排除。高作答率并不保证识别正确；这只约束当前固定组合，软容量等替代方法仍需另测。</p></div></section>
  <section id="lab-defence" class="lab-defence"><div class="lab-section-head"><div><span class="lab-kicker">ATTACK CONDITIONS / 防护从哪里着手</span><h3>隐藏什么有用，什么可能没用？</h3></div><span class="lab-tag">输入条件测试 · 非部署防护</span></div><div class="lab-defence-grid"><div><h4>相同标称σ，误差结构不同</h4><p>正确分组、32访、未知尺度距离谱、λ=0。下列分数属于这个对照，不与上方固定惩罚主表混作同一方法。</p><div id="lab-defence-chart"></div></div><div class="lab-defence-copy"><article><b>只换原点、朝向或统一缩放</b><p>距离谱对刚体变换不变；归一化还会消除统一尺度。仅隐藏这些量，不足以阻断该类匹配。</p></article><article><b>破坏跨访问的稳定几何</b><p>共同平移被距离相减抵消；独立误差更易扭曲距离谱。它给出防护方向，但尚未测试在真实IMU上如何实现，以及正常功能会损失多少。</p></article><article><b>减少可关联的长期记录与环境先验</b><p>缩短可观察访问、限制跨会话关联、降低候选环境先验，是候选措施。缺少手表或地图不等于所有攻击失效；手机和相对关系仍可能含信息。</p></article></div></div></section>
  <div id="lab-defence-evidence" class="lab-defence-evidence"></div>
  <section id="lab-sources" class="lab-source-section"><div class="lab-section-head"><div><span class="lab-kicker">REPRODUCIBLE / 结果与展示同源</span><h3>把当前视图带走。</h3></div></div><div class="lab-downloads"><button id="lab-export-scene" type="button">当前观测图 SVG ↓</button><button id="lab-export-chart" type="button">当前队列对照 SVG ↓</button><button id="lab-export-csv" type="button">当前队列数据 CSV ↓</button><a href="research/simulation-index.json" download>指标与来源 JSON ↓</a><a href="research/defence-conditions.md" download>防护分析与边界 ↓</a></div><details><summary>查看输入来源、条件与限制</summary><p>给定32次事件坐标；闭600候选；随机游走末访每轴SD=.5m；固定λ=.0003。不是原始IMU波形仿真，不是ProcTHOR生成，不是开放集拒识或真实房屋恢复。新增衔接为事后探索。</p><p>全部600套、四路线可选，默认每族首个ID，不按分数挑例。物理时钟、真实房屋排名与泛化标志没有升级。</p><ul>${index.sources.map(s=>`<li><code>${esc(s.name)}</code><br><small>SHA256 ${s.sha256}</small></li>`).join('')}</ul></details></section>`;
  let family=index.families[0].id,houses=[],houseIndex=0,routeIndex=0,mode=1,visits=32,timer=null,page=0,version=0;
  const cache=new Map(),q=id=>root.querySelector('#'+id);
  const stop=()=>{clearInterval(timer);timer=null;q('lab-play').textContent='▶ 回放';};
  function atlas(){const start=page*20;q('lab-atlas-grid').innerHTML=houses.slice(start,start+20).map((h,i)=>`<button type="button" data-house-index="${start+i}" aria-label="选择${h.id}" aria-pressed="${start+i===houseIndex}">${thumbnail(h)}<span>${h.id}</span></button>`).join('');q('lab-atlas-page').textContent=`${page+1} / 5`;q('lab-atlas-prev').disabled=page===0;q('lab-atlas-next').disabled=page===4;}
  function show(){
    const h=houses[houseIndex];if(!h)return;const r=h.routes[routeIndex],m=r.methods[mode],credit=m.identity_top1;
    q('lab-truth').innerHTML=sceneSvg(h,r,{mode,visits,kind:'truth'});q('lab-observed').innerHTML=sceneSvg(h,r,{mode,visits,kind:'observed'});
    q('lab-truth-label').textContent=h.id+' / '+h.sites.length+'站位';q('lab-group-label').textContent=m.group_count+'个提议组';
    q('lab-progress').value=visits;q('lab-progress-value').textContent=`${visits} / 32`;
    q('lab-visits').innerHTML=r.site_ids.map((s,i)=>`<button type="button" data-visit="${i+1}" aria-label="查看访问${i+1}" aria-pressed="${i+1===visits}" class="${i+1>visits?'future':''}"><small>${i+1}</small>S${s}</button>`).join('');
    q('lab-record').innerHTML=`<div><span>当前记录身份得分</span><strong>${pct(credit)}</strong><small>${credit>0&&credit<1?'并列首选的解析期望':'固定600候选身份任务'}</small></div><div><span>可排名候选</span><strong>${m.candidate_count}<em> / 600</em></strong><small>候选需至少 ${m.group_count} 个站位</small></div><div><span>目标布局参评状态</span><strong class="${m.target_retained?'kept':'lost'}">${m.target_retained?'保留':'被排除'}</strong><small>${m.target_retained?'仅说明可参评，不保证首选正确':'不是拒绝作答；还可能给其它身份排名'}</small></div><div><span>表示别名</span><strong>${h.alias_ids.length}<em> 个身份</em></strong><small>${h.alias_ids.length===1?'当前0.2m表示下的单例':esc(h.alias_ids.join(' / '))}</small></div>`;
    q('lab-candidates').innerHTML=`<span>并列首选（${m.first_tie_count}）</span><div>${m.first_ties.map(id=>`<button type="button" data-candidate="${id}" title="打开该候选的合成布局">${id}${id===h.id?' · 真值':''}</button>`).join('')||'<b>全库无可排名候选</b>'}${m.first_ties_truncated?'<small>仅列前12个ID，指标仍按全部并列计算</small>':''}</div>`;
    q('lab-relation-matrix').innerHTML=relationMatrixSvg(r,mode);
    q('lab-relation-text').innerHTML=`<h4>评价侧 · 496对关系</h4><p>每一格是一对访问。它们共享32个节点，不是496个独立会话。</p><ul><li><i style="background:#418D81"></i>同地找对 TP <b>${m.relation.tp}</b></li><li><i style="background:#AD764D"></i>异地误并 FP <b>${m.relation.fp}</b></li><li><i style="background:#A8BED1"></i>同地漏掉 FN <b>${m.relation.fn}</b></li><li><i style="background:#EAF0F5"></i>异地分开 TN <b>${m.relation.tn}</b></li></ul>`;
    q('lab-house').value=houseIndex;root.querySelectorAll('[data-mode]').forEach(b=>b.setAttribute('aria-pressed',Number(b.dataset.mode)===mode));
  }
  function results(){const rows=aggregateRows(index,q('lab-cohort').value);q('lab-chart').innerHTML=chartSvg(rows);q('lab-result-table').innerHTML=table(['方法','全部查询身份top-1','整房95%区间','作答率','已答身份top-1','目标候选保留'],rows.map(r=>[r.title,pct(r.rate.value),r.ci.map(pct).join(' – '),`${r.answer.numerator}/${r.answer.denominator} · ${pct(r.answer.value)}`,pct(r.precision.value),`${r.retained.numerator}/${r.retained.denominator} · ${pct(r.retained.value)}`]));}
  async function chooseFamily(id,selectedId=null){
    stop();family=id;const token=++version;root.setAttribute('aria-busy','true');
    try{let data=cache.get(id);if(!data){const manifest=await request('simulation-'+id+'.json');const parts=await Promise.all(manifest.parts.map(p=>request(p.file)));data={houses:parts.flatMap(p=>p.houses)};if(data.houses.length!==100)throw Error('房型分片不完整');cache.set(id,data);}if(token!==version)return;houses=data.houses;houseIndex=selectedId?Math.max(0,houses.findIndex(h=>h.id===selectedId)):0;page=Math.floor(houseIndex/20);visits=32;
      q('lab-house').innerHTML=houses.map((h,i)=>`<option value="${i}">${h.id} · ${h.sites.length}站位${h.cohort==='alias'?' · 有别名':''}</option>`).join('');
      root.querySelectorAll('[data-family]').forEach(b=>b.setAttribute('aria-pressed',b.dataset.family===id));atlas();show();
    }catch(e){q('lab-record').textContent=e.message;}finally{if(token===version)root.removeAttribute('aria-busy');}
  }
  root.addEventListener('click',e=>{
    const b=e.target.closest('button');if(!b)return;
    if(b.dataset.family)chooseFamily(b.dataset.family);
    if(b.dataset.mode!==undefined){stop();mode=Number(b.dataset.mode);show();}
    if(b.dataset.visit){stop();visits=Number(b.dataset.visit);show();}
    if(b.dataset.houseIndex){stop();houseIndex=Number(b.dataset.houseIndex);visits=32;show();atlas();}
    if(b.dataset.candidate){const c=index.catalogue.find(x=>x.id===b.dataset.candidate);if(c)chooseFamily(c.family,c.id);}
  });
  q('lab-house').addEventListener('change',()=>{stop();houseIndex=Number(q('lab-house').value);visits=32;page=Math.floor(houseIndex/20);atlas();show();});
  q('lab-route').addEventListener('change',()=>{stop();routeIndex=Number(q('lab-route').value);visits=32;show();});
  q('lab-next').addEventListener('click',()=>{stop();houseIndex=(houseIndex+1)%houses.length;visits=32;page=Math.floor(houseIndex/20);show();atlas();});
  q('lab-atlas-prev').addEventListener('click',()=>{page=Math.max(0,page-1);atlas();});q('lab-atlas-next').addEventListener('click',()=>{page=Math.min(4,page+1);atlas();});
  q('lab-progress').addEventListener('input',()=>{stop();visits=Number(q('lab-progress').value);show();});
  q('lab-play').addEventListener('click',()=>{if(timer){stop();return;}if(visits===32)visits=1;q('lab-play').textContent='Ⅱ 暂停';show();timer=setInterval(()=>{visits++;show();if(visits>=32)stop();},window.matchMedia('(prefers-reduced-motion: reduce)').matches?1100:500);});
  document.addEventListener('visibilitychange',()=>{if(document.hidden)stop();});
  q('lab-cohort').addEventListener('change',results);
  q('lab-export-scene').addEventListener('click',()=>download(`synthetic-${houses[houseIndex].id}-route${routeIndex+1}-${index.modes[mode]}.svg`,sceneSvg(houses[houseIndex],houses[houseIndex].routes[routeIndex],{mode,visits,kind:'observed'}),'image/svg+xml'));
  q('lab-export-chart').addEventListener('click',()=>download('synthetic-ranking-'+q('lab-cohort').value+'.svg',chartSvg(aggregateRows(index,q('lab-cohort').value)),'image/svg+xml'));
  q('lab-export-csv').addEventListener('click',()=>{const cohort=q('lab-cohort').value,rows=aggregateRows(index,cohort);const lines=[['cohort','method','identity_numerator','queries','identity_top1','ci_low','ci_high','answer_numerator','answer_rate','answered_identity_top1','retained_numerator','target_retention','representation_reference'],...rows.map(r=>[cohort,r.mode,r.rate.numerator,r.rate.denominator,r.rate.value,...r.ci,r.answer.numerator,r.answer.value,r.precision.value,r.retained.numerator,r.retained.value,r.ceiling])];download('synthetic-ranking-'+cohort+'.csv','\uFEFF'+lines.map(r=>r.join(',')).join('\r\n'),'text/csv;charset=utf-8');});
  const def=defenceRows(index),names={none:'无噪声参照',common:'共同平移',brownian:'随机游走',iid:'独立误差'};
  q('lab-defence-chart').innerHTML=def.map(r=>`<div class="lab-noise-row"><span>${names[r.structure]}</span><div><i style="width:${r.top1*100}%;background:${r.structure==='iid'?'#AD764D':r.structure==='brownian'?'#3974D8':'#8196A4'}"></i></div><b>${pct(r.top1)}</b></div>`).join('')+'<p class="lab-footnote">误差档σ=.5m；共同平移是数学不变性控制，原运行复用无噪声分数，不能作为独立重复。σ不是实测位置RMS，正常功能代价未评测。</p>';
  await initDefence(q('lab-defence-evidence')).catch(e=>{q('lab-defence-evidence').textContent=e.message;});
  results();await chooseFamily(family);
  if(location.hash.startsWith('#lab-'))document.querySelector('[data-tab="trajectory"]')?.click();
}
if(typeof document!=='undefined'){
  const root=document.getElementById('simulation-lab');
  if(root)initSimulation(root).catch(e=>{root.innerHTML=`<p class="note">${esc(e.message)}，未用示意数据替代。</p>`;});
}
