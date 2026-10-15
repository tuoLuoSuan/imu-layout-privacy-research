import http from 'node:http';
import {readFile, lstat, realpath} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';
const defaultRoot=path.dirname(fileURLToPath(import.meta.url));
// Reviewed browser assets only. Private examples stay local and outside Git.
const assets=new Set([
  '/index.html','/style.css','/app.mjs','/data.mjs',
  '/data/first-session.json','/data/phone-config-smoke.json',
  '/assets/recorder-0.2.2-records.png',
  '/node_modules/three/build/three.module.js',
  '/node_modules/three/build/three.core.js',
  '/node_modules/three/examples/jsm/controls/OrbitControls.js',
]);
const types={'.html':'text/html; charset=utf-8','.css':'text/css; charset=utf-8',
  '.mjs':'text/javascript; charset=utf-8','.js':'text/javascript; charset=utf-8',
  '.json':'application/json; charset=utf-8','.png':'image/png'};

export function createShowcaseServer({root=defaultRoot}={}) {
  return http.createServer(async(req,res)=>{
    if(!['GET','HEAD'].includes(req.method)) {
      res.writeHead(405,{'Allow':'GET, HEAD'});res.end();return;
    }
    try {
      let name=decodeURIComponent(new URL(req.url,'http://localhost').pathname);
      if(name==='/')name='/index.html';
      if(!assets.has(name))throw Error('unreviewed asset');
      const base=await realpath(root);
      let target=base;
      for(const part of name.slice(1).split('/')) {
        target=path.join(target,part);
        if((await lstat(target)).isSymbolicLink())throw Error('linked asset');
      }
      const actual=await realpath(target),rel=path.relative(base,actual);
      if(rel.startsWith('..')||path.isAbsolute(rel))throw Error('outside root');
      const bytes=await readFile(actual);
      res.writeHead(200,{'Content-Type':types[path.extname(actual)],'Cache-Control':'no-store',
        'X-Content-Type-Options':'nosniff'});
      res.end(req.method==='HEAD'?undefined:bytes);
    } catch {
      res.writeHead(404,{'Content-Type':'text/plain; charset=utf-8'});res.end(req.method==='HEAD'?undefined:'文件不存在');
    }
  });
}

if(process.argv[1]&&pathToFileURL(path.resolve(process.argv[1])).href===import.meta.url) {
  const port=Number(process.env.IMU_SHOWCASE_PORT??8765);
  if(!Number.isInteger(port)||port<1||port>65535)throw Error('Invalid IMU_SHOWCASE_PORT');
  const server=createShowcaseServer();
  server.listen(port,'127.0.0.1',()=>console.log(`IMU research workbench: http://127.0.0.1:${port}`));
  server.on('error',e=>{console.error(e.message);process.exitCode=1;});
}
