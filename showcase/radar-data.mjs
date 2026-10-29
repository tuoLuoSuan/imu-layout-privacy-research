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
export function groupRadarPoints(points,bounds,{hideUpper=false,upperLimit=2.2}={}){
  const groups={room:[],balcony:[],other_outside:[]};let hiddenUpper=0;
  for(const point of points){
    if(hideUpper&&point[2]>upperLimit){hiddenUpper++;continue;}
    groups[pointRegion(point,bounds)].push(point);
  }
  return {groups,hiddenUpper,displayable:points.length-hiddenUpper};
}
