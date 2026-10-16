// Only normalise entries returned for this application's fixed files directory.
// The extra separator was observed on S5; never take basename of an arbitrary path.
const ROOT='internal://files/';
function normalize(entries){
 if(!Array.isArray(entries))throw Error('文件列表返回格式异常，请保留文件检查结果');
 const seen=Object.create(null),out=[];
 entries.forEach(entry=>{
  if(!entry||typeof entry.uri!=='string')return;
  let name=entry.uri;
  if(name.indexOf(ROOT)===0){name=name.slice(ROOT.length);if(name.charAt(0)==='/')name=name.slice(1);}
  if(!/^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/.test(name)||seen[name])return;
  seen[name]=true;out.push({uri:ROOT+name});
 });
 return out;
}
module.exports={normalize:normalize};
