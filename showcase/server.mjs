import http from 'node:http';
import {readFile, lstat, realpath} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';
const defaultRoot=path.dirname(fileURLToPath(import.meta.url));
// Reviewed browser assets only. Private examples stay local and outside Git.
const assets=new Set([
  '/defence.mjs','/research/defence-evidence.json',
  '/research/defence-conditions.md',
  '/simulation.mjs','/simulation.css','/research/simulation-index.json',
  '/research/simulation-dorm.json','/research/simulation-apartment.json','/research/simulation-conference.json',
  '/research/simulation-office.json','/research/simulation-classroom.json','/research/simulation-hotel.json',
  '/research/simulation-dorm-1.json','/research/simulation-dorm-2.json',
  '/research/simulation-apartment-1.json','/research/simulation-apartment-2.json',
  '/research/simulation-conference-1.json','/research/simulation-conference-2.json',
  '/research/simulation-office-1.json','/research/simulation-office-2.json',
  '/research/simulation-classroom-1.json','/research/simulation-classroom-2.json',
  '/research/simulation-hotel-1.json','/research/simulation-hotel-2.json',
  '/research.mjs','/research.css','/research/current-evidence.json','/research/current-status.md',
  '/assets/checkpoint-20261029-prototype-and-prior-boundaries.png',
  '/assets/checkpoint-20261029-prototype-and-prior-boundaries.svg',
  '/assets/checkpoint-20261029-prototype-and-prior-boundaries.pdf',
  '/assets/checkpoint-20261029-event-error-boundaries.png',
  '/assets/checkpoint-20261029-event-error-boundaries.svg',
  '/assets/checkpoint-20261029-event-error-boundaries.pdf',
  '/assets/checkpoint-20261029-real-and-out-of-family-audit.png',
  '/assets/checkpoint-20261029-real-and-out-of-family-audit.svg',
  '/assets/checkpoint-20261029-real-and-out-of-family-audit.pdf',
  '/assets/checkpoint-20261029-results.md',
  '/assets/checkpoint-20261029-next-step.md',
  '/data/checkpoint-20261029-summary.json',

  '/assets/automatic-20261029-oracle-controls.png',
  '/assets/automatic-20261029-oracle-controls.svg',
  '/assets/automatic-20261029-oracle-controls.pdf',
  '/assets/automatic-20261029-automatic-stops.png',
  '/assets/automatic-20261029-automatic-stops.svg',
  '/assets/automatic-20261029-automatic-stops.pdf',
  '/assets/automatic-20261029-automatic-clock-scenarios.png',
  '/assets/automatic-20261029-automatic-clock-scenarios.svg',
  '/assets/automatic-20261029-automatic-clock-scenarios.pdf',
  '/assets/automatic-stops-closeout-20261029.md',

  '/index.html','/style.css','/app.mjs','/data.mjs',
  '/radar.mjs','/radar-data.mjs',
  '/dorm-units.mjs','/dorm-unit-view.mjs',
  '/data/latest-signal-catalog-20261028.json',
  '/data/signal-20261027-anchor90-phone-accel.json',
  '/data/signal-20261027-anchor90-phone-gyro.json',
  '/data/signal-20261027-anchor90-watch-accel.json',
  '/data/latest-research-evidence-20261028.json',
  '/data/latest-research-export-verification-20261028.json',
  '/assets/latest-20261027-actions-on-trajectory.png',
  '/assets/latest-20261028-frontend-controls.png',
  '/assets/latest-20261028-frontend-controls.svg',
  '/assets/latest-20261028-frontend-controls.pdf',
  '/assets/latest-20261028-temporal-holdout.png',
  '/assets/latest-20261028-temporal-holdout.svg',
  '/assets/latest-20261028-temporal-holdout.pdf',
  '/assets/latest-20261028-identifiability.png',
  '/assets/latest-20261028-identifiability.svg',
  '/assets/latest-20261028-identifiability.pdf',
  '/assets/latest-20261028-audit-controls.png',
  '/assets/latest-20261028-audit-controls.svg',
  '/assets/latest-20261028-audit-controls.pdf',
  '/assets/position-reference-amendment-20261028.md',
  '/assets/relative-20261029-revisit-results.png',
  '/assets/relative-20261029-revisit-results.svg',
  '/assets/relative-20261029-revisit-results.pdf',
  '/assets/relative-20261029-relative-positions.png',
  '/assets/relative-20261029-relative-positions.svg',
  '/assets/relative-20261029-relative-positions.pdf',
  '/assets/relative-places-results-20261029.md',
  '/assets/joint180-results-and-next-step-20261029.md',
  '/assets/latest-20261029-joint180-reference-pass.png',
  '/assets/latest-20261029-joint180-reference-pass.svg',
  '/assets/latest-20261029-joint180-reference-pass.pdf',
  '/assets/latest-20261029-joint180-conditional-holdout.png',
  '/assets/latest-20261029-joint180-conditional-holdout.svg',
  '/assets/latest-20261029-joint180-conditional-holdout.pdf',
  '/assets/reference-20261029-g3-confirmation.png',
  '/assets/reference-20261029-g3-confirmation.svg',
  '/assets/reference-20261029-g3-confirmation.pdf',
  '/assets/reference-20261029-g3-sensitivity.png',
  '/assets/reference-20261029-g3-sensitivity.svg',
  '/assets/reference-20261029-g3-sensitivity.pdf',
  '/assets/reference-20261029-reference-availability.png',
  '/assets/reference-20261029-reference-availability.svg',
  '/assets/reference-20261029-reference-availability.pdf',
  '/assets/next-joint-reference-20261029.md',
  '/data/signal-20261025-bed-phone-accel.json',
  '/data/signal-20261025-bed-phone-gyro.json',
  '/data/signal-20261025-bed-watch-accel.json',
  '/data/signal-20261025-ground-phone-accel.json',
  '/data/signal-20261025-ground-phone-gyro.json',
  '/data/signal-20261025-ground-watch-accel.json',
  '/data/signal-20261025-calibration-phone-accel.json',
  '/data/signal-20261025-calibration-phone-gyro.json',
  '/data/signal-20261025-calibration-watch-accel.json',
  '/data/latest-signal-catalog-20261026.json',
  '/data/dorm-room-20261026.json','/data/dorm-points-20261026.json',
  '/data/dorm-room-20261027.json','/assets/room-semantics-20261027.png','/assets/room-stability-20261027.png',
  '/data/dorm-points-full-20261027.json',
  '/assets/room-polygon-20261026.png',
  '/assets/room-density-20261026.png',
  '/assets/room-bands-20261026.png',
  '/assets/room-elevation-20261026.png',

  '/data/first-session.json','/data/phone-config-smoke.json',
  '/assets/recorder-0.2.2-records.png',
  '/node_modules/three/build/three.module.js',
  '/node_modules/three/build/three.core.js',
  '/node_modules/three/examples/jsm/controls/OrbitControls.js',
]);
const types={'.html':'text/html; charset=utf-8','.css':'text/css; charset=utf-8',
  '.mjs':'text/javascript; charset=utf-8','.js':'text/javascript; charset=utf-8',
  '.json':'application/json; charset=utf-8','.png':'image/png',
  '.svg':'image/svg+xml','.pdf':'application/pdf','.md':'text/plain; charset=utf-8'};

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
