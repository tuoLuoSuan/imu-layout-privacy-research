// Discardable identity hints only: never selection, deletion hashes or consent.
const ROOT='internal://files/',CACHE=ROOT+'s5view_cache_v1.json',REV=ROOT+'s5view_revision_v1.txt';
const safe=s=>typeof s==='string'&&/^[A-Za-z0-9_-]{1,64}$/.test(s);
function valid(hints){
 if(!Array.isArray(hints)||hints.length>256)return false;const seen={};
 return hints.every(r=>{if(!Array.isArray(r)||r.length!==3||!safe(r[0])||!safe(r[1])||['i','f'].indexOf(r[2])<0)return false;const key=r.join('|');if(seen[key])return false;seen[key]=true;return true;});
}
function call(file,method,uri,text){return new Promise(resolve=>{
 let done=false;const timer=setTimeout(()=>finish({ok:false}),3000);
 function finish(r){if(done)return;done=true;clearTimeout(timer);resolve(r);}
 try{if(!file||typeof file[method]!=='function')return finish({ok:false});const options={uri:uri,
  success:v=>finish({ok:true,text:v&&v.text}),fail:(m,c)=>finish({ok:false,missing:Number(c)===301})};
  if(method==='writeText'){options.text=text;options.append=false;}file[method](options);}catch(e){finish({ok:false});}
});}
function revision(file){return call(file,'readText',REV).then(r=>r.missing?'':r.ok&&typeof r.text==='string'&&/^[A-Za-z0-9_-]{1,64}:[A-Za-z0-9_-]{1,64}$/.test(r.text)?r.text:null);}
function load(file){
 return revision(file).then(first=>call(file,'readText',CACHE).then(r=>revision(file).then(last=>{
  const out={hints:null,revision:last,status:'miss'};if(first===null||last!==first||!r.ok||typeof r.text!=='string'||r.text.length>65536)return out;
  try{const v=JSON.parse(r.text);if(Object.keys(v).sort().join('|')==='hints|revision|schema'&&v.schema===1&&v.revision===last&&valid(v.hints)){out.hints=v.hints;out.status='cached';}}catch(e){}return out;
 })));
}
function save(file,hints,rev){
 if(!valid(hints)||typeof rev!=='string')return Promise.resolve({ok:false});
 const text=JSON.stringify({schema:1,revision:rev,hints:hints});if(text.length>65536)return Promise.resolve({ok:false});
 return call(file,'writeText',CACHE,text);
}
function invalidate(file,s){
 if(!s||!safe(s.native_sid)||!safe(s.sid))return Promise.resolve({ok:false});
 return call(file,'writeText',REV,s.native_sid+':'+s.sid);
}
module.exports={load:load,save:save,invalidate:invalidate,valid:valid};
