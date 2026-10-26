export function pointRegion(point,bounds){
  if(point[0]>bounds.x[1])return 'balcony';
  return point[0]>=bounds.x[0]&&point[1]>=bounds.y[0]&&point[1]<=bounds.y[1]?'room':'other_outside';
}
export function validateRadarSummary(summary){
  const count=Object.values(summary.counts).reduce((a,b)=>a+b,0);
  if(count!==summary.total_points)throw Error('Inconsistent point counts');
  if(summary.geometry_verified!==false||summary.formal_score!==null)throw Error('Room remains a candidate');
  return summary;
}
