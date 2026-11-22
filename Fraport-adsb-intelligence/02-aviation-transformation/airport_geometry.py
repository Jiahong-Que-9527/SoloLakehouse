"""Local-plane airport geometry built from a supplied OSM snapshot."""
import xml.etree.ElementTree as ET

import numpy as np
from matplotlib.path import Path as Polygon
from scipy.spatial import cKDTree


def load_geometry(directory):
    def xy(lat,lon):
        return (lon-8.5706)*71500,(lat-50.0333)*110570
    nodes, ways, stands = {}, {}, {}
    for path in sorted(directory.glob('geometry-*.osm')):
        root=ET.parse(path).getroot()
        for n in root.findall('node'):
            p=xy(float(n.get('lat')),float(n.get('lon')))
            nodes[n.get('id')]=p
            if n.find("tag[@k='aeroway'][@v='parking_position']") is not None:
                stands[n.get('id')]=p
        for w in root.findall('way'):
            tag=w.find("tag[@k='aeroway']")
            if tag is not None:
                ref=w.find("tag[@k='ref']")
                ways[w.get('id')]=(tag.get('v'),ref.get('v') if ref is not None else '',[n.get('ref') for n in w.findall('nd')])
    geom={}
    for k,ref,ids in ways.values():
        if all(i in nodes for i in ids):
            geom.setdefault(k,[]).append((ref,np.array([nodes[i] for i in ids])))
    for i,(_,p) in enumerate(geom.get('parking_position',[])):
        if len(p): stands['way'+str(i)]=p.mean(axis=0)
    ST=np.array(list(stands.values()))
    RW=[(ref,p) for ref,p in geom['runway'] if len(p)>1 and not np.array_equal(p[0],p[-1])]
    TX=[p for _,p in geom['taxiway'] if len(p)>1]
    APR=[Polygon(p,closed=True) for _,p in geom['apron'] if len(p)>=4 and np.array_equal(p[0],p[-1])]
    assert len(ST)>30 and len(RW)>=4 and len(TX)>20 and APR

    def segdist(xy,paths):
        a=np.concatenate([p[:-1] for p in paths]); b=np.concatenate([p[1:] for p in paths])
        v=b-a; den=np.maximum((v*v).sum(1),1e-6)
        result=[]
        for x in np.array_split(xy,max(1,len(xy)//128+1)):
            d=x[:,None,:]-a
            u=np.clip((d*v).sum(2)/den,0,1)
            result.extend(np.sqrt(((d-u[:,:,None]*v)**2).sum(2).min(1)))
        return np.array(result)
    def build_taxi_index():
        starts, ends = [], []
        for p in TX:
            for a,b in zip(p[:-1],p[1:]):
                n=max(1,int(np.ceil(np.linalg.norm(b-a)/70)))
                grid=np.linspace(a,b,n+1)
                starts.extend(grid[:-1])
                ends.extend(grid[1:])
        a,b=np.asarray(starts),np.asarray(ends)
        v=b-a
        return a,v,np.maximum((v*v).sum(1),1e-6),cKDTree((a+b)/2)
    TI=build_taxi_index()
    def taxi_dist(points):
        a,v,den,tree=TI
        buckets=tree.query_ball_point(points,136)
        result=np.full(len(points),np.inf)
        indices=np.repeat(np.arange(len(points)),[len(x) for x in buckets])
        if len(indices):
            segments=np.concatenate(buckets).astype(int)
            d=points[indices]-a[segments]
            heading=v[segments]
            t=np.clip((d*heading).sum(1)/den[segments],0,1)
            values=np.linalg.norm(d-t[:,None]*heading,axis=1)
            np.minimum.at(result,indices,values)
        return result
    def gdist(xy, *, with_stands=True):
        r=np.stack([segdist(xy,[p]) for _,p in RW],axis=1)
        tx=taxi_dist(xy)
        stand=np.sqrt(((xy[:,None,:]-ST)**2).sum(2).min(1)) if with_stands else None
        apron=np.any([p.contains_points(xy) for p in APR],axis=0)
        return r,tx,stand,apron
    return gdist, [ref for ref, _ in RW], {
        "runways": len(RW), "taxiways": len(TX), "aprons": len(APR), "stands": len(ST)
    }
