import http from 'node:http';
import {readFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root=path.dirname(fileURLToPath(import.meta.url));
const types={'.html':'text/html; charset=utf-8','.css':'text/css; charset=utf-8','.js':'text/javascript; charset=utf-8','.mjs':'text/javascript; charset=utf-8','.json':'application/json; charset=utf-8','.png':'image/png','.md':'text/plain; charset=utf-8'};
const server=http.createServer(async(req,res)=>{
  if(!['GET','HEAD'].includes(req.method)){res.writeHead(405);res.end();return;}
  try{
    const name=decodeURIComponent(new URL(req.url,'http://localhost').pathname);
    const target=path.resolve(root,'.'+(name==='/'?'/index.html':name));
    const rel=path.relative(root,target);
    if(rel.startsWith('..')||path.isAbsolute(rel)){res.writeHead(403);res.end();return;}
    const bytes=await readFile(target);
    res.writeHead(200,{'Content-Type':types[path.extname(target)]||'application/octet-stream','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'});
    res.end(req.method==='HEAD'?undefined:bytes);
  }catch{res.writeHead(404);res.end('文件不存在');}
});
server.listen(8765,'127.0.0.1',()=>console.log('IMU research workbench: http://127.0.0.1:8765'));
server.on('error',e=>{console.error(e.message);process.exitCode=1;});
