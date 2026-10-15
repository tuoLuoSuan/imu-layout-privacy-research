// Standalone layout preview from the actual UX template/style. Not a Vela runtime or data capture.
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const ux = fs.readFileSync(path.join(root, 'variants/research-ui/src/Probe/index.ux'), 'utf8');
const template = ux.match(/<template>([\s\S]*?)<\/template>/)[1];
const style = ux.match(/<style>([\s\S]*?)<\/style>/)[1];
const icon = 'data:image/png;base64,' + fs.readFileSync(path.join(root, 'variants/research-ui/src/common/icon.png')).toString('base64');
const target = process.argv[2];
if (!target) throw Error('Pass an output HTML file; no server or hardware is started');
const encoded = JSON.stringify({template, style, icon}).replace(/</g, '\\u003c');
const html = `<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>S5统一界面 · 布局预览</title>
<style>body{margin:0;background:#e8edf3;font-family:"Microsoft YaHei",sans-serif;color:#102a43}main{max-width:850px;margin:32px auto;text-align:center}h1{font-size:24px;margin:0 0 8px}p{margin:6px 0;font-size:15px;color:#52677c}#watch{width:466px;height:466px;border-radius:50%;overflow:hidden;margin:28px auto;background:#f3f6fa;box-shadow:0 0 0 12px #24323d,0 20px 42px #102a4326}#watch div{display:flex;flex-shrink:0;box-sizing:border-box}#watch span{display:block;flex-shrink:0;box-sizing:border-box}#watch img{flex-shrink:0}#watch .status{line-height:20px}#watch [data-qr-placeholder]{justify-content:center;align-items:center;border:1px dashed #52677c;color:#52677c;font-size:16px;text-align:center}button{padding:10px 16px;margin:4px;border:0;border-radius:12px;background:#176b6d;color:white;cursor:pointer}.button,.parameter,.navitem,.retry{cursor:pointer}</style>
<main><h1>手机同款 · S5腕部界面</h1><p id="evidence-label">布局预览 · 非手表实测 · 不连接传感器或设备</p><div id="watch"></div><div><button onclick="demo('collect')">采集页</button><button onclick="demo('records')">记录页</button><button onclick="demo('settings')">设置页</button><button onclick="demo('qr')">二维码区域</button></div><p>沿用手机图标和配色，按圆屏排布；尚未安装或验收真机渲染。</p></main>
<script>const source=${encoded};document.head.insertAdjacentHTML('beforeend','<style>'+source.style+'</style>');
const state={version:'0.2.0',tab:'collect',settingsMode:false,exportMode:false,recording:false,saving:false,hasRecord:false,status:'准备就绪',elapsed:'0.0',samples:0,x:'--',y:'--',z:'--',labelText:'静止',durationSeconds:2,qrIndex:0,qrTotal:1,autoText:'已暂停',qrValue:''};
function value(expression){return Function('s','with(s){return ('+expression+')}')(state)}
function bind(text){return text.replace(/{{([\\s\\S]*?)}}/g,(_,e)=>value(e))}
function render(){const temp=document.createElement('template');temp.innerHTML=source.template.replace(/<text(\\s|>)/g,'<span$1').replace(/<\\/text>/g,'</span>').replace(/<image /g,'<img ').replace(/<\\/image>/g,'').replace(/<qrcode /g,'<div data-qr-placeholder ').replace(/<\\/qrcode>/g,'</div>');
function walk(node){if(node.nodeType===3){node.textContent=bind(node.textContent);return}if(node.nodeType!==1)return;
const gate=node.getAttribute('if');if(gate&&!value(gate.replace(/^{{|}}$/g,''))){node.remove();return}node.removeAttribute('if');
for(const attr of Array.from(node.attributes)){if(attr.name==='onclick'){node.setAttribute('data-action',attr.value);node.removeAttribute('onclick')}else node.setAttribute(attr.name,bind(attr.value))}
if(node.tagName==='IMG')node.src=source.icon;if(node.hasAttribute('data-qr-placeholder'))node.textContent='二维码区域（布局示意）';
for(const child of Array.from(node.childNodes))walk(child)}for(const child of Array.from(temp.content.childNodes))walk(child);document.getElementById('watch').replaceChildren(temp.content);
if(state.exportMode)document.querySelector('.qrinfo').textContent='页码与轮播状态（布局示意）'}
function demo(mode){state.tab=mode==='records'?'records':'collect';state.settingsMode=mode==='settings';state.exportMode=mode==='qr';state.status='准备就绪';render()}
document.getElementById('watch').addEventListener('click',e=>{const control=e.target.closest('[data-action]');if(!control)return;const a=control.dataset.action;
if(a==='showCollect')demo('collect');else if(a==='showRecords')demo('records');else if(a==='openSettings')demo('settings');else if(a==='closeSettings')demo('collect');else if(a==='closeExport')demo('records');else if(a==='choose2'||a==='choose10'||a==='choose30'){state.durationSeconds=Number(a.slice(6));render()}else if(a==='chooseStill'||a==='chooseWalk'||a==='chooseArm'){state.labelText={chooseStill:'静止',chooseWalk:'走路',chooseArm:'摆手'}[a];render()}else{state.status='布局预览，不执行设备操作';render()}});render();</script></html>`;
fs.mkdirSync(path.dirname(path.resolve(target)), {recursive: true});
fs.writeFileSync(target, html);
console.log(path.resolve(target));
