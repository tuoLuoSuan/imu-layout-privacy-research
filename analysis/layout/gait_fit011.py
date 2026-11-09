"""Exploratory parametric gait inversion, separate from the frozen011 primary.

This uses the simulator's smooth-motion family and must not be presented as
independent evidence of real-world inertial accuracy. No scene/pose truth is
accepted. Unknown duration, phase, stride and amplitude can be fitted to raw
six-axis samples; inverse-model mismatch needs separate validation.
"""
import numpy as np
from scipy.optimize import least_squares
from .sim_motion import U_UP,basis_from_up


def template(t,distance,duration,phase,stride=.5,scale=1.):
    t=np.asarray(t,float);u=np.clip(t/duration,0.,1.);active=(t>=0)&(t<=duration);s=u**3*(10-15*u+6*u*u);ds=30*u*u*(1-u)**2/duration;dds=60*u*(1-u)*(1-2*u)/duration**2
    g=np.sin(np.pi*u)**2;dg=np.pi/duration*np.sin(2*np.pi*u);ddg=2*np.pi**2/duration**2*np.cos(2*np.pi*u);phi=phase+2*np.pi*distance*s/stride;dp=2*np.pi*distance*ds/stride;ddp=2*np.pi*distance*dds/stride
    z2=ddg*np.sin(phi)+2*dg*np.cos(phi)*dp+g*(np.cos(phi)*ddp-np.sin(phi)*dp*dp);c2=ddg*np.cos(phi)-2*dg*np.sin(phi)*dp-g*(np.sin(phi)*ddp+np.cos(phi)*dp*dp)
    forward=(distance*dds+.06*scale*z2)*active;side=.02*scale*c2*active;vertical=.025*scale*z2*active
    angles=np.c_[.04*g*np.sin(phi),.10*g*np.sin(phi+.3),.03*g*np.sin(phi+.7)]*scale
    rates=np.c_[.04*(dg*np.sin(phi)+g*np.cos(phi)*dp),.10*(dg*np.sin(phi+.3)+g*np.cos(phi+.3)*dp),.03*(dg*np.sin(phi+.7)+g*np.cos(phi+.7)*dp)]*scale*active[:,None]
    x,y,z=angles.T;dx,dy,dz=rates.T;gyro=np.c_[dx-dz*np.sin(y),dy*np.cos(x)+dz*np.sin(x)*np.cos(y),-dy*np.sin(x)+dz*np.cos(x)*np.cos(y)]
    v=np.c_[-side,forward,vertical+9.81]@basis_from_up(U_UP['walk']);a=v[:,0]*np.cos(z)+v[:,1]*np.sin(z);b=-v[:,0]*np.sin(z)+v[:,1]*np.cos(z);c=v[:,2];a,c=a*np.cos(y)-c*np.sin(y),a*np.sin(y)+c*np.cos(y);b,c=b*np.cos(x)+c*np.sin(x),-b*np.sin(x)+c*np.cos(x)
    return np.c_[a,b,c],gyro


def fit(time,acceleration,gyro,initial_distance):
    t=np.asarray(time,float);A=np.asarray(acceleration,float);G=np.asarray(gyro,float);begin=t[0];total=t[-1]-begin;dt=np.median(np.diff(t));step=max(1,round(.025/dt));t=t[::step];A=A[::step];G=G[::step];A=A-A.mean(axis=0);G=G-G.mean(axis=0);extent=min(1.5,total*.3);initial=max(.06,float(initial_distance));best=None
    def residual(p):
        length,lo,hi,phase,stride,scale=p;a,g=template(t-begin-lo,length,total-lo-hi,phase,stride,scale);a-=a.mean(axis=0);g-=g.mean(axis=0)
        return np.r_[((a-A)/.08).ravel(),((g-G)/.012).ravel()]
    lower=[max(.02,initial*.5),0.,0.,-10.,.4,.6];upper=[max(.2,initial*1.7+.1),extent,extent,10.,.6,1.4]
    for phase in [-np.pi,-np.pi/2,0.,np.pi/2,np.pi]:
        seed=[initial,min(.5,extent*.6),min(.5,extent*.6),phase,.5,1.];r=least_squares(residual,seed,bounds=(lower,upper),max_nfev=100,loss='soft_l1',f_scale=2.)
        if best is None or r.cost<best.cost:best=r
    return {'distance_m':float(best.x[0]),'begin_offset_s':float(best.x[1]),'end_offset_s':float(best.x[2]),'phase':float(best.x[3]),'stride_m':float(best.x[4]),'gait_scale':float(best.x[5]),'mean_scaled_residual':float(np.mean(residual(best.x)**2)),'scope':'Model-based synthetic gait diagnostic, not independent real validation'}
