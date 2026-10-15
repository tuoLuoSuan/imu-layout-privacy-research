// Stop-and-wait export only. No sensor calls, file mutation or background uploads.
function crc32(text){let c=-1;for(let i=0;i<text.length;i++){c^=text.charCodeAt(i);for(let j=0;j<8;j++)c=(c>>>1)^(0xedb88320&-(c&1));}return('00000000'+((c^-1)>>>0).toString(16)).slice(-8);}
function integer(n){return typeof n==='number'&&isFinite(n)&&Math.floor(n)===n;}
function createSender(options){
  const now=options.now||Date.now;let status='idle',error='',source=null,part=0,offset=0,body='',checksum='',token='',pending=null,generation=0;
  function state(){return {status:status,error:error,part:part,parts:source?source.parts:0,offset:offset,length:body.length,
    percent:source?Math.floor(100*(part+(body.length?offset/body.length:0))/source.parts):0};}
  function notify(){if(options.onStatus)options.onStatus(state());}
  function fail(message){status='failed';error=String(message);pending=null;notify();}
  function transmit(){
    if(status!=='sending')return;
    const current=pending;
    current.sent=now();
    try{options.send(current.text,e=>{if(pending===current&&status==='sending')fail(e||'消息发送失败');});}
    catch(e){fail(e.message||e);}
  }
  function sendNext(){
    const message={p:'S5TX1',t:token,s:source.session,m:source.format,i:part,n:source.parts,o:offset,l:body.length,c:checksum,d:body.slice(offset,offset+1024)};
    pending={text:JSON.stringify(message),message:message,retries:0,sent:now()};status='sending';notify();transmit();
  }
  function load(index,alreadyRead){
    const mine=generation;part=index;offset=0;pending=null;status='loading';notify();
    return (alreadyRead===undefined?source.readPart(index):Promise.resolve(alreadyRead)).then(text=>{
      if(mine!==generation||status==='cancelled')return;
      if(typeof text!=='string'||!text.length||text.length>65536||/[^\x00-\x7f]/.test(text))throw Error('导出分段必须为非空ASCII，且不超过64KiB');
      body=text;checksum=crc32(text);sendNext();
    }).catch(e=>{if(mine===generation)fail(e.message||e);});
  }
  return {
    state:state,
    start:function(value){
      generation++;pending=null;source=value;part=0;offset=0;body='';error='';status='loading';
      if(!value||!/^[A-Za-z0-9_-]{1,80}$/.test(value.session)||['v2','legacy1'].indexOf(value.format)<0||!integer(value.parts)||value.parts<1||value.parts>403||typeof value.readPart!=='function'||(value.format==='legacy1'&&value.parts!==1)){
        fail('导出来源无效');return Promise.resolve();
      }
      const mine=generation;notify();
      return Promise.resolve().then(()=>value.readPart(0)).then(first=>{
        if(mine!==generation)return;
        token=crc32(value.format+'|'+value.session+'|'+value.parts+'|'+first)+crc32(first+'|'+value.session+'|S5TX1');
        return load(0,first);
      }).catch(e=>{if(mine===generation)fail(e.message||e);});
    },
    receive:function(text){
      if(status!=='sending'||!pending)return;
      try{
        if(text&&typeof text==='object')text=text.data;
        if(typeof text!=='string'||text.length>4096)return;
        const ack=JSON.parse(text),m=pending.message;
        if(ack.p==='S5ERR1'&&ack.t===token&&ack.s===source.session){fail(ack.error||'接收端拒绝');return;}
        if(ack.p!=='S5ACK1'||ack.t!==token||ack.s!==source.session||ack.i!==part||ack.c!==checksum||!integer(ack.o)||ack.o<=m.o||ack.o>body.length)return;
        if(ack.o===body.length&&ack.state!=='part_complete')return;
        offset=ack.o;pending=null;
        if(offset===body.length){
          if(part+1===source.parts){status='complete';notify();return;}
          load(part+1);
        }else sendNext();
      }catch(e){} // Unrelated ordinary messages are ignored, never interpreted as commands.
    },
    tick:function(){
      if(status!=='sending'||!pending)return;
      if(now()<pending.sent){fail('传输计时时钟倒退，请重试');return;}
      if(now()-pending.sent<2000)return;
      if(pending.retries>=3){fail('接收端未确认，请确认插件已准备接收后重试');return;}
      pending.retries++;transmit();
    },
    disconnect:function(){if(status==='sending'||status==='loading')fail('连接已断开，保留原记录，可重试');},
    cancel:function(){generation++;pending=null;status='cancelled';notify();}
  };
}
module.exports={createSender:createSender,crc32:crc32};
