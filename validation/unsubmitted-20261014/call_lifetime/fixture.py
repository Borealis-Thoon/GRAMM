"""Small synthetic GRAMM inputs, no research data."""
from pathlib import Path
import json
from geometry_fixture import write_geometry,validate_geometry

def make_case(folder, *, nx=24,ny=20,nz=16,dx=250,threads=1,sc=4,wind=2.0,duration=360,dt=5,irad=30,custom=False,coast=False,multi=False,radiation=True,turbulence=False):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=False)
    grid=dict(nx=nx,ny=ny,nz=nz,dx_m=dx,dy_m=dx,first_dz_m=20.,vertical_stretch=1.3 if nz<=16 else 1.2,terrain_height_m=0.,west_m=0,south_m=0)
    write_geometry(folder/'ggeom.asc',grid)
    qa=validate_geometry(folder/'ggeom.asc',grid)
    (folder/'geometry_validation.json').write_text(json.dumps(qa,indent=2))
    (folder/'GRAMM.geb').write_text('\n'.join(map(str,[nx,ny,nz,0,int(nx*dx),0,int(ny*dx)]))+'\n')
    surface=[(1800,0.5,0.1,0.15,0.92,0.19) if not coast or i>=nx//2 else (1000,2.,0.0001,1.,0.98,0.08) for j in range(ny) for i in range(nx)]
    (folder/'landuse.asc').write_text('\n'.join(' '.join(str(p[k]) for p in surface) for k in range(6))+'\n')
    labels=['date','start','max timestep','duration','output','w deviation','RH percent','lowest height','air K','lapse','neutral height','surface K','soil K','latitude','IRAD','debug','UVW PN T','BR PR QU PSI TE TB STR','diagnostic','implicit','RELAXV','RELAXT','catabatic','ERA5 interval','boundary','ISTAT','reinitialization','nesting','format']
    values=[20220621,600,dt,duration,3600,.01,60,0,288.15,-.0065,5000,288.15,288.15,47.,irad,0,1111100,(1110011 if radiation else 1110010)+(100 if turbulence else 0),1,1,.2,.2,0,6,6,0,24,0,0]
    (folder/'IIN.dat').write_text('\n'.join(f'{k}: {v}' for k,v in zip(labels,values))+'\n')
    (folder/'GRAMMin.dat').write_text('Version 17.01\ny\n0.2\n1,0\nyes\n0\n')
    (folder/'Max_Proc.txt').write_text(str(threads)+'\n')
    mets=[(27,wind,sc,1)] if not multi else [(27,2,4,.34),(9,1,7,.33),(18,3,2,.33)]
    (folder/'meteopgt.all').write_text('10,1,10\ndirection,speed,stability,frequency\n'+'\n'.join(','.join(map(str,m)) for m in mets)+'\n')
    if custom:
        extra=['1000,285.15,283.15,286.15,-1.5,0.85,250,-0.0065,0.012,-0.004','2000,302.9,303.65,293.15,1.5,0.55,1000,-0.005,0.009,-0.006','0,288.15,0,0,0,0.92,0,0,0,0']
        (folder/'CustomInit.txt').write_text('GRAMM custom initial conditions; values at sea level\nheader\n'+'\n'.join(','.join(map(str,m))+','+extra[i%3] for i,m in enumerate(mets))+'\n')
    config=dict(grid=grid,threads=threads,sc=sc,wind=wind,duration=duration,dt=dt,irad=irad,custom=custom,coast=coast,multi=multi,situations=len(mets),radiation=radiation,turbulence=turbulence)
    (folder/'fixture.json').write_text(json.dumps(config,indent=2))
    return config
