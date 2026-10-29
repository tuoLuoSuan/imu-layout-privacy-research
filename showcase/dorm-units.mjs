// Display-only regions. No furniture detection, physical footprints or query labels.
export function makeFourUnitDraft(summary){
  const [x0,x1]=summary.room.x,[y0,y1]=summary.room.y,gap=summary.corridor_m;
  if(![x0,x1,y0,y1,gap].every(Number.isFinite)||x1-x0<2||y1-y0<=gap||gap<=0)throw Error('Valid registered outer frame and aisle required');
  const xm=(x0+x1)/2,ym=(y0+y1)/2;
  const near=[x0+.32,xm-.12],far=[xm+.12,x1-.32];
  const left=[ym+gap/2+.06,y1-.07],right=[y0+.07,ym-gap/2-.06];
  const positions=[
    {id:1,side:'left',depth:'near',name:'左近',detail:'左侧 · 靠入户',xx:near,yy:left,color:'#427FA8'},
    {id:2,side:'left',depth:'far',name:'左远',detail:'左侧 · 靠阳台',xx:far,yy:left,color:'#4D927C'},
    {id:3,side:'right',depth:'near',name:'右近',detail:'右侧 · 靠入户',xx:near,yy:right,color:'#B88B4B'},
    {id:4,side:'right',depth:'far',name:'右远',detail:'右侧 · 靠阳台',xx:far,yy:right,color:'#827BA8'},
  ];
  return {schema:'four-unit-user-labelled-display-v2',purpose:'two desks near entrance and two beds near balcony, as directly specified by user',
    view_reference:'standing at entrance facing balcony; +x forward, +y left',
    room:{...summary.room,x:[x0,x1],y:[y0,y1]},corridor_m:gap,
    positioning_rule:'two per side; equal longitudinal split with illustrative margins; not measured unit boundaries',
    units:positions.map(({xx,yy,...unit})=>({...unit,
      center_xy_m:[(xx[0]+xx[1])/2,(yy[0]+yy[1])/2],
      illustrative_bounds_m:[xx[0],yy[0],xx[1],yy[1]],
      kind:[1,3].includes(unit.id)?'desk':'bed',assignment_status:'user_confirmed',
      semantic_source:'direct user reply: 1,3 desks; 2,4 beds',furniture_geometry_measured:false})),
    planned_program:{bed:2,desk:2,chair:2},
    aisle_objects:[1,3].map(id=>({id:`chair-for-${id}`,kind:'chair',
      center_xy_m:[(near[0]+near[1])/2,ym+(id===1?1:-1)*(gap/2-.28)],associated_unit_id:id,
      facing_side:id===1?'left':'right',source:'user clarified two desks should have two chairs',
      position_source:'illustrative at the front of the associated desk, not measured',geometry_measured:false})),
    user_assignment_confirmed:true,
    aisle_clutter_hidden_in_schematic:true,
    real_object_detection:false,geometry_truth_verified:false,usable_as_attack_observation:false,formal_score:null};
}

// Positive x is to the right; positive room y is up on this display only.
export function projectDormPlan(draft){
  const [x0,x1]=draft.room.x,[y0,y1]=draft.room.y,L=x1-x0,W=y1-y0;
  return {aspect_ratio:L/W,entry_side:'left',balcony_side:'right',
    units:draft.units.map(unit=>{
      const [a,b,c,d]=unit.illustrative_bounds_m;
      return {id:unit.id,left:100*(a-x0)/L,top:100*(y1-d)/W,width:100*(c-a)/L,height:100*(d-b)/W};
    }),
    chairs:draft.aisle_objects.map(chair=>({associated_unit_id:chair.associated_unit_id,
      left:100*(chair.center_xy_m[0]-x0)/L,top:100*(y1-chair.center_xy_m[1])/W,
      width:100*.46/L,height:100*.46/W}))};
}
