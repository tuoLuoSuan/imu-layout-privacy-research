function once(source,from,to){
  if(source.split(from).length!==2)throw Error('Progressive duration marker mismatch: '+from.slice(0,90));
  return source.replace(from,to);
}
function core(source){
  let out=once(source,"app_version:'0.4.8'","app_version:'0.4.9'");
  out=once(out,'const DURATIONS = [2, 10, 30, 60, 180, 300, 1800];',
    'const DURATIONS = [2, 10, 30, 60, 180, 300, 600, 900, 1200, 1800];');
  return once(out,'timed_flush_ms:duration===1800?8000:2000','timed_flush_ms:duration>=600?8000:2000');
}
function page(source){
  return once(once(source,'v0.4.8','v0.4.9'),'[2,10,30,60,180,300,1800]',
    '[2,10,30,60,180,300,600,900,1200,1800]');
}
module.exports={core,page};
