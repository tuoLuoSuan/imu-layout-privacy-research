// Optional discovery metadata written only after the original acquisition completes.
// A locator is never ownership proof or permission to delete a session.
const viewCache=require('./view-cache.js'),ROOT='internal://files/';let revision=0;
const safe=s=>typeof s==='string'&&/^[A-Za-z0-9_-]{1,64}$/.test(s);
function uri(v){return ROOT+'s5loc_'+v.native_sid+'_'+v.sid+'.json';}
function decode(path,v){
 if(!v||Object.keys(v).sort().join('|')!=='dir|kind|native_sid|schema|sid'||v.schema!==1||v.kind!=='session_locator'||!safe(v.native_sid)||!safe(v.sid)||v.dir!==ROOT+'s5joint_'+v.native_sid+'_'+v.sid+'/'||path!==uri(v))return null;
 return v;
}
function remember(file,s){
 if(!s||s.phase!=='complete'||!safe(s.native_sid)||!safe(s.sid)||s.session_root_uri!==ROOT+'s5joint_'+s.native_sid+'_'+s.sid+'/')return Promise.resolve({status:'skipped'});
 const value={schema:1,kind:'session_locator',native_sid:s.native_sid,sid:s.sid,dir:s.session_root_uri},path=uri(value),text=JSON.stringify(value);
 return viewCache.invalidate(file,s).then(invalidation=>new Promise(resolve=>{
  let done=false;const timer=setTimeout(()=>finish('unavailable'),5000);
  function finish(status){if(done)return;done=true;clearTimeout(timer);if(status==='saved')revision++;resolve({status:status==='saved'&&!invalidation.ok?'unavailable':status});}
  try{file.readText({uri:path,success:r=>finish(r&&r.text===text?'saved':'unavailable'),fail:(m,c)=>{
   if(done)return;if(Number(c)!==301)return finish('unavailable');
   try{file.writeText({uri:path,text:text,append:false,success:()=>finish('saved'),fail:()=>finish('unavailable')});}catch(e){finish('unavailable');}
  }});}catch(e){finish('unavailable');}
 })).then(result=>{if(result.status!=='saved')return result;return require('./catalog-index.js').add(file,[s.native_sid,s.sid,'i']).then(r=>({status:r.ok?'saved':'unavailable'}));});
}
module.exports={decode:decode,remember:remember,revision:()=>revision};
