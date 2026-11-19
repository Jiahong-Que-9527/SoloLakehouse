"""Exploratory historical EDDF crossing observability pilot; all outputs local."""
import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from silver_m1 import digest, read_manifest, source_hours

DEFAULT_CROSSING = {
    "south_connector": "M8",
    "north_connector": "L5",
    "holding_point_xy_m": None,
    "geometry_status": "provisional_osm_not_historical_aip",
}
DEPARTURE_COLUMNS = (
    "dep_entry_lo", "dep_entry_hi", "dep_end_lo", "dep_end_hi",
    "dep_first_inside_t", "dep_last_inside_t", "dep_inside_points", "dep_ground_traverse_m",
)
def cid(d,icao,t):return f'{d}:{icao}:{int(t)}'
def xy(lat,lon):return np.stack([(np.asarray(lon)-8.5706)*71500,(np.asarray(lat)-50.0333)*110570],axis=-1)
def geometry(directory, config):
    nodes={}; ways={}
    for file in sorted(directory.glob('geometry-*.osm')):
        root=ET.parse(file).getroot()
        for n in root.findall('node'):
            nodes[n.get('id')]=(xy(float(n.get('lat')),float(n.get('lon'))),{t.get('k'):t.get('v') for t in n.findall('tag')})
        for w in root.findall('way'):
            tags={t.get('k'):t.get('v') for t in w.findall('tag')}
            if tags.get('aeroway') in ('runway','taxiway'):
                ways[w.get('id')]=(tags,[n.get('ref') for n in w.findall('nd')])
    ways=[(t,i) for t,i in ways.values() if all(n in nodes for n in i) and len(i)>1]
    rw={}
    for t,ids in ways:
        if t.get('aeroway')=='runway' and ids[0]!=ids[-1]:
            a,b=sorted((nodes[ids[0]][0],nodes[ids[-1]][0]),key=lambda x:-x[0])
            u=(b-a)/np.linalg.norm(b-a)
            v=np.array([u[1],-u[0]])
            if v[1]<0:v=-v
            rw[t['ref']]=(a,u,v,np.linalg.norm(b-a),float(t['width']))
    m8=[ids for t,ids in ways if t.get('ref')==config['south_connector'] and t.get('aeroway')=='taxiway']
    l5=[ids for t,ids in ways if t.get('ref')==config['north_connector'] and t.get('aeroway')=='taxiway']
    center=[ids for t,ids in ways if t.get('ref')=='07C/25C' and t.get('aeroway')=='runway' and ids[0]!=ids[-1]][0]
    common=set(n for ids in m8 for n in ids)&set(n for ids in l5 for n in ids)&set(center)
    assert len(common)==1
    cross=nodes[common.pop()][0]
    approach=next(ids for ids in m8 if any(np.linalg.norm(nodes[n][0]-cross)<0.1 for n in ids)
                  and any(nodes[n][1].get('holding_position:type')=='runway' for n in ids))
    hold_ids=[n for n in approach if nodes[n][1].get('holding_position:type')=='runway']
    assert len(hold_ids)==1
    hold=nodes[hold_ids[0]][0] if config["holding_point_xy_m"] is None else np.array(config["holding_point_xy_m"])
    return rw,cross,hold,nodes[hold_ids[0]][1],np.array([nodes[n][0] for n in approach])
def axes(p, rw):
    return (p-rw[0])@rw[1], (p-rw[0])@rw[2]
def window(lo=None,hi=None):
    return (float(lo),float(hi)) if lo is not None and hi is not None and 0<hi-lo<=30 else (None,None)
def events(t, points, fragments, center, cross_point, hold_point):
    t=np.asarray(t)
    x,y=axes(points,center)
    cx,_=axes(cross_point,center)
    hx,hy=axes(hold_point,center)
    # A strip aligned along the south connector, narrowing as it meets the runway.
    expected=cx+(hx-cx)*np.clip(y/hy,0,1.8)
    near=np.abs(x-expected)<=42
    strip=(np.abs(y)<=center[4]/2)&(np.abs(x-cx)<=50)
    south=y < -center[4]/2
    north=(y>center[4]/2)&(np.abs(x-cx)<75)
    hold_zone=near & (y>=hy-12)&(y < -center[4]/2)
    approach=near & (y<hy-12)&(y>hy-155)
    cross=None; hold=None; across=None
    for j in np.flatnonzero(strip):
        left=np.flatnonzero(near[:j]&south[:j]&(t[:j]>=t[j]-120))
        right=np.flatnonzero(north[j+1:]&(t[j+1:]<=t[j]+90))+j+1
        if not len(left) or not len(right):continue
        k,i=left[-1],right[0]
        # Crossing recognition can survive sparse evidence; timestamp stays unresolved.
        if np.max(np.diff(t[k:i+1]))>30 or not np.all(fragments[k:i+1]==fragments[j]):continue
        cross=window(t[k],t[j]); across=float(t[i]); break
    eligible_h=np.flatnonzero(hold_zone&(t<=cross[1] if cross and cross[1] is not None else True))
    for j in eligible_h:
        k=j-1
        if k>=0 and approach[k] and fragments[k]==fragments[j]:
            hold=window(t[k],t[j])
            if hold[0] is not None:break
    visible_other=False
    for k in range(len(t)-2):
        if not (y[k]<-center[4]/2 and abs(x[k]-cx)>120):continue
        if abs(y[k+1])<=center[4]/2 and abs(x[k+1]-x[k])<120 and y[k+2]>center[4]/2 and abs(x[k+2]-x[k+1])<120 and fragments[k]==fragments[k+2]:
            visible_other=True;break
    if hold and cross and hold[1] > cross[1]:hold=None
    return {'in_connector':bool(near[y<0].any()),'hold_zone_observed':bool(hold_zone.any()),
            'runway_strip_observed':bool(strip.any()),
            'other_center_crossing_pattern':visible_other,
            'hold_lo':hold[0] if hold else None,'hold_hi':hold[1] if hold else None,
            'cross_lo':cross[0] if cross else None,'cross_hi':cross[1] if cross else None,
            'across_observed_t':across}
def arrival_direction(r, q, south):
    if r.estimated_runway_axis!='07R/25L' or not r.runway_air_to_ground_observed:return 'unclassified_axis_or_transition'
    if q.empty:return 'unclassified_direction'
    p=xy(q.latitude,q.longitude); x,y=axes(p,south)
    t=q.position_epoch_s.to_numpy()
    z=np.flatnonzero((abs(y)<=36)&(x>=-100)&(x<=south[3]+100)&(t<=t[0]+125))
    if len(z)<2:return 'unclassified_direction'
    delta=x[z[-1]]-x[z[0]]
    return '25L' if delta>=150 else '07R' if delta<=-150 else 'unclassified_direction'
def airborne_departure_axis(q, anchor, runways):
    air=q[(~q.g)&q.obs.between(anchor-180,anchor+200)]
    if len(air)<3:return None
    coords=xy(air.lat,air.lon)
    choices=[]
    for ref,rw in runways.items():
        x,y=axes(coords,rw)
        for sign,number in ((1,1),(-1,0)):
            names=ref.split('/')
            if len(names)==1 and ((rw[1][1]<0)!=(sign==1)):continue
            u=x if sign==1 else rw[3]-x
            good=np.flatnonzero((abs(y)<=110)&(u>=rw[3]-1200)&(u<=rw[3]+2000))
            if len(good)<3:continue
            i,j=good[0],good[-1]
            ts=air.obs.iloc[j]-air.obs.iloc[i]
            if not 0<ts<=35 or u[j]-u[i]<220 or abs(y[j]-y[i])>100:continue
            name=names[number] if len(names)==2 else ref
            choices.append((float(np.median(abs(y[good]))),name))
    if not choices:return None
    choices.sort()
    if len(choices)>1 and choices[1][0]-choices[0][0]<25:return None
    return choices[0][1]

def departure(q, anchor, runways):
    if len(q)<5:return {'dep_runway':'unknown','dep_reason':'sparse'}
    q=q.sort_values(['obs','t']).drop_duplicates('obs')
    t=q.obs.to_numpy(); ground=q.g.to_numpy()
    z=xy(q.lat,q.lon)
    candidates=[]
    for ref,rw in runways.items():
        x,y=axes(z,rw)
        inside=(abs(y)<=rw[4]/2+8)&(x>=-30)&(x<=rw[3]+30)&ground
        for j in np.flatnonzero((ground[:-1])&(~ground[1:]))+1:
            if t[j]-t[j-1]>30 or not inside[j-1]:continue
            idx=np.flatnonzero(inside[:j]&(t[:j]>=t[j]-100))
            if len(idx)<3:continue
            delta=x[idx[-1]]-x[idx[0]]
            projection=x[j]-x[idx[-1]]
            if abs(delta)<350 or np.sign(delta)*projection < 10 or abs(y[j])>100:continue
            names=ref.split('/')
            if len(names)==2:
                # West-oriented axis for parallels; first label is eastbound.
                name=names[1] if delta>0 else names[0]
            else:
                lat0=q.lat.iloc[idx[0]]; lat1=q.lat.iloc[idx[-1]]
                if lat1>=lat0:continue
                name=ref
            # Use latest entry before the confirmed ground roll; split at discontinuities.
            k=j-1
            while k>0 and inside[k-1] and t[k]-t[k-1]<=30:k-=1
            prior=k-1
            start=window(t[prior],t[k]) if prior>=0 and not inside[prior] and ground[prior] else (None,None)
            end=window(t[j-1],t[j])
            candidates.append((t[j],-abs(delta),dict(dep_runway=name,dep_reason='roll_air_transition',
                dep_entry_lo=start[0],dep_entry_hi=start[1],dep_end_lo=end[0],dep_end_hi=end[1],
                dep_first_inside_t=float(t[k]),dep_last_inside_t=float(t[j-1]),
                dep_inside_points=j-k,dep_ground_traverse_m=float(abs(delta)))))
    if candidates:return min(candidates,key=lambda a:a[:2])[2]
    runway=airborne_departure_axis(q, anchor, runways)
    return {'dep_runway':runway or 'unknown','dep_reason':'airborne_axis_only' if runway else 'no_directional_roll_transition'}
def load_departures(con, root, day, runways, records):
    path=root/"metadata/manifests/days"/f"dt={day}"/"flights.json"
    src,status=read_manifest(root,path,"eddf_flights",records,day+"T00:00:00Z")
    if src is None:raise ValueError(f"Departure cohort unavailable for {day}: {status}")
    d=con.execute("""select lower(icao24) icao24,firstseen anchor
       from read_parquet(?) where estdepartureairport='EDDF' and icao24 is not null and firstseen is not null
       group by 1,2 order by 2,1""",[str(src)]).df()
    d['id']=[cid(day,a,b) for a,b in zip(d.icao24,d.anchor)]
    files,issues=source_hours(root,int(d.anchor.min())-900,int(d.anchor.max())+300,records) if len(d) else ([],[])
    if not files:
        return [dict(id=r.id,day=day,icao24=r.icao24,anchor=r.anchor,dep_runway='unknown',
                     dep_reason='no_complete_source') for r in d.itertuples(index=False)], pd.DataFrame(
                     columns=['id','t','obs','lat','lon','g']), issues
    con.register('dep',d)
    s=con.execute("""select d.id,s.time t,s.lastposupdate obs,s.lat,s.lon,s.onground g
     from read_parquet(?) s join dep d on s.icao24=d.icao24 and s.time between d.anchor-900 and d.anchor+300
     where s.lat between 49.998 and 50.065 and s.lon between 8.49 and 8.63
       and s.onground is not null and s.lastposupdate between s.time-15 and s.time+2
     qualify row_number() over(partition by s.icao24,s.time,s.lastposupdate,s.lat,s.lon,s.onground order by abs(s.time-d.anchor),d.id)=1
     order by d.id,s.lastposupdate,s.time,s.lat,s.lon""",[files]).df()
    con.unregister('dep')
    tracks=dict(tuple(s.groupby('id')))
    r=[]
    for row in d.itertuples(index=False):
        result=departure(tracks.get(row.id,pd.DataFrame()), row.anchor, runways)
        r.append(dict(id=row.id,day=day,icao24=row.icao24,anchor=row.anchor,**result))
    points=s[s.id.isin({r['id'] for r in r if r['dep_runway']=='25C'})].copy()
    points=points.sort_values(['id','obs','t','lat','lon']).drop_duplicates(['id','obs'])
    points['gap_from_previous_s']=points.groupby('id').obs.diff()
    points['break_before']=points.gap_from_previous_s.gt(30)
    return r,points,issues
def align(arr, deps, issues):
    if pd.isna(arr.hold_lo):return 'hold_time_unknown',0,0
    nearby=deps[(deps.day==arr.day)&(deps.anchor.between(arr.hold_lo-600,arr.hold_hi+600))]
    center=deps[(deps.day==arr.day)&(deps.dep_runway=='25C')]
    definite=center[(center.dep_first_inside_t<=arr.hold_lo)&(center.dep_last_inside_t>=arr.hold_hi)]
    possible=center[(center.dep_entry_lo.fillna(center.dep_first_inside_t-120)<=arr.hold_hi)&
                    (center.dep_end_hi>=arr.hold_lo)]
    unresolved=int(((nearby.dep_runway=='unknown')|((nearby.dep_runway=='25C')&nearby.dep_first_inside_t.isna())).sum())
    if len(definite):return 'observed_departure_occupied',len(definite),unresolved
    if len(possible):return 'occupancy_boundary_uncertain',len(possible),unresolved
    incomplete=any(h<=arr.hold_hi+600 and h+3600>arr.hold_lo-600 for h,_ in issues)
    if unresolved or nearby.empty or incomplete:return 'insufficient_departure_coverage',0,unresolved
    return 'no_observed_overlap_proxy',0,0

def apply_occupancy_alignment(ap, deps, issues):
    states=['occupancy_at_hold','possible_25c_departures','nearby_unclassified_departures']
    ap[states]=pd.DataFrame([align(row,deps,issues) if row.direction=='25L' else ('not_in_target_cohort',0,0)
                            for row in ap.itertuples(index=False)],columns=states,index=ap.index)
    ap['joint_occupied_observed']=ap.both_arrival_events & ap.occupancy_at_hold.eq('observed_departure_occupied')
    # Source-only no overlap is not evidence that the runway was free.
    ap['joint_unoccupied_confirmed']=False
    ap['joint_source_only_including_no_overlap']=ap.both_arrival_events & ap.occupancy_at_hold.isin(
        ['observed_departure_occupied','no_observed_overlap_proxy'])


def run(args):
    root, geo, silver, out = (p.resolve() for p in
                             (args.bronze_root, args.geometry_dir, args.arrival_silver, args.output))
    repo=Path(__file__).resolve().parents[2]
    if any(out.is_relative_to(p) for p in (repo, root, geo, silver)):
        raise ValueError("Output must be a new local directory outside the repository and inputs")
    if out.exists():raise FileExistsError(out)
    manifest=json.loads((silver/'run_manifest.json').read_text())
    if manifest['dates_utc'] != [args.date]:
        raise ValueError("Arrival Silver must contain exactly the selected UTC date")
    for name in ('arrival_coverage.parquet','surface_points.parquet'):
        if digest(silver/name)!=manifest['outputs'][name]['sha256']:
            raise ValueError(f"Invalid input artifact: {name}")
    config=DEFAULT_CROSSING | (json.loads(args.crossing_config.read_text()) if args.crossing_config else {})
    runways,cross,hold,hold_tag,_=geometry(geo,config)
    center,south=runways['07C/25C'],runways['07R/25L']
    con=duckdb.connect()
    con.execute('set threads=2')
    a=con.read_parquet(str(silver/'arrival_coverage.parquet')).df()
    points=con.read_parquet(str(silver/'surface_points.parquet')).df().sort_values(['arrival_id','position_epoch_s'])
    groups=dict(tuple(points.groupby('arrival_id',sort=False)))
    arrivals=[]
    fields=dict.fromkeys(('in_connector','hold_zone_observed','runway_strip_observed','other_center_crossing_pattern',
                          'hold_lo','hold_hi','cross_lo','cross_hi','across_observed_t'))
    for r in a.itertuples(index=False):
        q=groups.get(r.arrival_id,pd.DataFrame())
        direction=arrival_direction(r,q,south)
        e=fields
        if direction=='25L':
            e=events(q.position_epoch_s.to_numpy(),xy(q.latitude,q.longitude),q.fragment_no.to_numpy(),
                     center,cross,hold)
        arrivals.append(dict(id=r.arrival_id,day=args.date,icao24=r.icao24,anchor=r.arrival_anchor_epoch_s,
                            direction=direction,**e))
    acols=['id','day','icao24','anchor','direction',*fields]
    ap=pd.DataFrame(arrivals,columns=acols)
    for col in ('hold_lo','hold_hi','cross_lo','cross_hi','across_observed_t'):
        ap[col]=pd.to_numeric(ap[col])
    ap['wait_lo_s']=(ap.cross_lo-ap.hold_hi).clip(lower=0)
    ap['wait_hi_s']=ap.cross_hi-ap.hold_lo
    ap['both_arrival_events']=ap.wait_lo_s.notna() & ap.wait_hi_s.notna() & ap.wait_hi_s.ge(0)
    records={}
    dp,dep_points,issues=load_departures(con,root,args.date,runways,records)
    deps=pd.DataFrame(dp).reindex(columns=['id','day','icao24','anchor','dep_runway','dep_reason',*DEPARTURE_COLUMNS])
    for col in DEPARTURE_COLUMNS:
        deps[col]=pd.to_numeric(deps[col])
    apply_occupancy_alignment(ap, deps, issues)
    out.mkdir(mode=0o700,parents=False,exist_ok=False)
    outputs={}
    for name,frame in (('arrival_event_evidence',ap),('departure_occupancy_evidence',deps),
                       ('departure_25c_observations',dep_points)):
        f=out/(name+'.parquet')
        con.register('output_frame',frame)
        con.table('output_frame').write_parquet(str(f),compression='zstd')
        con.unregister('output_frame')
        outputs[f.name]={"rows":len(frame),"sha256":digest(f)}
    (out/'run_manifest.json').write_text(json.dumps({
        "day_utc":args.date,"input_silver_manifest_sha256":digest(silver/'run_manifest.json'),
        "bronze_manifests":records,"source_partition_issues":issues,"crossing":config,
        "geometry_hashes":{f.name:digest(f) for f in sorted(geo.glob('geometry-*.osm'))},
        "original_osm_holding_point_tags":hold_tag,"script_sha256":digest(Path(__file__)),
        "dependency_lock_sha256":digest(Path(__file__).with_name("uv.lock")),"outputs":outputs,
    },indent=2,sort_keys=True)+"\n")
    print(args.date,{key:value['rows'] for key,value in outputs.items()},flush=True)


if __name__=='__main__':
    from datetime import date
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--date',required=True,type=lambda text:date.fromisoformat(text).isoformat())
    for name in ('bronze-root','geometry-dir','arrival-silver','output'):
        parser.add_argument('--'+name,required=True,type=Path)
    parser.add_argument('--crossing-config',type=Path)
    run(parser.parse_args())
