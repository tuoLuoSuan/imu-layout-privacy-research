"""Oracle sensitivity only: align pose gauges before geodesic interpolation.

Never used by raw-signal inference. Initial true attitude/position are permitted
only in this labelled evaluation diagnostic, not an operational correction.
"""
import numpy as np
from scipy.spatial.transform import Rotation


def align(predicted,rotations,truth,truth_rotations):
    p,R,q,S=map(np.asarray,(predicted,rotations,truth,truth_rotations));Q=R[0]@S[0].T
    return (q-q[0])@Q[:2,:2].T+p[0],Q@S


def blend(predicted,rotations,truth,truth_rotations,alpha):
    if not 0<=alpha<=1:raise ValueError('Blend fraction in[0,1] required')
    p,R=map(np.asarray,(predicted,rotations));q,S=align(p,R,truth,truth_rotations);delta=Rotation.from_matrix(np.swapaxes(R,1,2)@S).as_rotvec()
    return (1-alpha)*p+alpha*q,R@Rotation.from_rotvec(alpha*delta).as_matrix()
