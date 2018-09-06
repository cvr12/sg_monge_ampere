 import matplotlib
matplotlib.use('Agg')

import numpy as np
from periodic_densities import Periodic_density_in_x, sample_rectangle
import MongeAmpere as ma
import matplotlib.pyplot as plt
import matplotlib.pyplot as plt
import matplotlib.tri as tri
import os

def initialise_points(N, bbox, RegularMesh = None):
    '''Function to initialise a mesh over the domain [-L,L]x[0,H]
    and transform to geostrophic coordinates

    args:
    N: number of grid points in z direct, total number of points
      will be 2*N*N

    RegularMesh: controls whether the mesh is regular or an optimised
                 sample of random points in the domain 

    returns:
    
    A numpy array of coordinates of points in geostrophic space
    '''
    H = bbox[3]
    L = bbox[2]

    if RegularMesh:
        npts = N
        dx = 1./npts
        s = np.arange(dx*0.5,1.,dx)
        s1 = np.arange(-1. + dx*0.5,1.,dx)
        x,z = np.meshgrid(s1*L,s*H)
        nx = x.size
        x = np.reshape(x,(nx,))
        z = np.reshape(z,(nx,))
        y = np.array([x,z]).T
        
    else:
        npts = 2*N*N
        bbox = np.array([0., -0.5, 2., 0.5])
        Xdens = sample_rectangle(bbox);
        f0 = np.ones(4)/2;
        w = np.zeros(Xdens.shape[0]); 
        T = ma.delaunay_2(Xdens,w);
        Sdens = Periodic_density_in_x(Xdens,f0,T,bbox)
        X = ma.optimized_sampling_2(Sdens,npts,niter=5)
        x = X[:,0]*L - L
        z = (X[:,1]+0.5)*H
        y = np.array([x,z]).T

    Nsq = 2.5e-5
    g = 10.
    f = 1.e-4
    theta0 = 300
    C = 3e-6
    B = 0.255
    #B = 1.0e-3* Nsq * theta0 * H / g
    thetap = Nsq*theta0*z/g + B*np.sin(np.pi*(x/L + z/H))
    vg = B*g*H/L/f/theta0*np.sin(np.pi*(x/L + z/H)) - 2*B*g*H/np.pi/L/f/theta0*np.cos(np.pi*x/L)
    
    X = vg/f + x
    Z = g*thetap/f/f/theta0
    Y = np.array([X,Z]).T
    return Y, thetap
    
def eady_OT(Y, bbox, dens, eps_g = 1.e-7,verbose = False):
    H = bbox[3]
    nx = Y[:,0].size
    nu = np.ones(nx)
    nu = (dens.mass() / np.sum(nu)) * nu
    
    w = 0.*Y[:,0]
    Z = Y[:,1]
    mask = Z>0.9*H
    w[mask] = (Z[mask] - 0.9*H)**2
    mask = Z<0.1*H
    w[mask] = (Z[mask] - 0.1*H)**2

    w = ma.optimal_transport_2(dens,Y,nu, w0=w, eps_g=1.0e-5,verbose=False)
    return w

def forward_euler_sg(Y, dens, tf, bbox, h=1800, t0=0., add_data = None):
    '''
    Function that finds time evolution of semi-geostrophic equations
    using forward Euler method
    
    args:
    
    Y initial data in Geostrophic co-ordinates
    h time step size
    
    returns:
    
    Y numpy array solution in physical co-ordinates at time tf
    '''
    
    H = bbox[3]
    L = bbox[2]
    Nsq = 2.5e-5
    g = 10.
    f = 1.e-4
    B = 0.255
    theta0 = 300
    C = 3e-6

    N = int(np.ceil((tf-t0)/h))

    os.mkdir('points_results')
    os.mkdir('weights_results')
    
    if add_data:
        KEmean = np.zeros(N+1)
        thetap = np.zeros(N+1)
        energy = np.zeros(N+1)
        vgmax = np.zeros(N+1)
        t = np.array([t0 + n*h for n in range(N+1)])
        
    for n in range(0,N+1):
        w = eady_OT(Y, bbox, dens)
        w.tofile('weights_results/weights_'+str(n)+'.txt',sep = " ",format = "%s")
        [Yc, m] = dens.lloyd(Y, w)
        
        if add_data:
            #calculate second moments to find KE and maximum of Vg
            [m1, I] = dens.moments(Y, w)  
            ke = f*f*0.5*(m*Y[:,0]**2 - 2*Y[:,0]*m1[:,0] + I[:,0])
            vg = f*(Y[:,0] - Yc[:,0])
            E = ke - f*f*Y[:,1]*m1[:,1] + 0.5*f*f*H*Y[:,1]*m
            energy[n] = np.sum(E)
            KEmean[n] = np.sum(ke)/float(Y[:,0].size)
            vgmax[n] = np.amax(vg) 

        if n == N:
            break
        
        #timestep using euler method
        Y[:,1] = Y[:,1] + h*C*g/f/theta0*(Y[:,0] - Yc[:,0])
        Y[:,0] = Y[:,0] + h*C*g/f/theta0*(Yc[:,1] - H*np.ones(Yc[:,1].size)/2.)

        #bring particles back to fundamental domain
        Y = dens.to_fundamental_domain(Y)
        Y.tofile('points_results/points_'+str(n+1)+'.txt',sep = " ",format = "%s")

    if add_data:
        return Y, w, energy, vgmax, KEmean, t
    else:
        return Y, w

def heun_sg(Y, dens, tf, bbox, h=1800, t0=0., add_data = None):
    '''
    Function that finds time evolution of semi-geostrophic equations
    using Heun's order 2 method
    
    args:
    
    Y initial data in Geostrophic co-ordinates
    dens 
    tf final time (seconds)
    bbox domain over which equations are being solved
    h time step size
    
    returns:
    
    Y numpy array solution in geostrophic co-ordinates at time tf
    w numpy array of weights associated with Y
    '''
    H = bbox[3]
    L = bbox[2]
    g = 10.
    f = 1.e-4
    theta0 = 300
    C = 3e-6

    N = int(np.ceil((tf-t0)/h))

    #create dummy array to store intermediate point values
    Yn = np.zeros(Y.shape)

    if add_data:
        KEmean = np.zeros(N+1)
        thetap = np.zeros(N+1)
        energy = np.zeros(N+1)
        vgmax = np.zeros(N+1)
        t = np.array([t0 + n*h for n in range(N+1)])
    
    for n in range(0,N+1):
        w = eady_OT(Y, bbox, dens)
        [Yc, m] = dens.lloyd(Y,w)

        if add_data:
            #calculate second moments to find KE and maximum of vg
            [m1, I] = dens.moments(Y, w)  
            ke = 0.5*f*f*(m*Y[:,0]**2 - 2*Y[:,0]*m1[:,0] + I[:,0])
            vg = f*(Y[:,0] - Yc[:,0])
            E = ke - f*f*Y[:,1]*m1[:,1] + 0.5*f*f*H*Y[:,1]*m
            energy[n] = np.sum(E)
            KEmean[n] = np.sum(ke)/float(Y[:,0].size)
            vgmax[n] = np.amax(vg)

        if n == N:
            break
        
        #timestep using heun's method
        Yn[:,1] = Y[:,1] + h*C*g/f/theta0*(Y[:,0] - Yc[:,0])
        Yn[:,0] = Y[:,0] + h*C*g/f/theta0*(Yc[:,1] - H*np.ones(Yc[:,1].size)/2.)
        w = eady_OT(Yn, bbox, dens)
        [Ycent, m] = dens.lloyd(Yn, w)
        Y[:,1] = Y[:,1] + 0.5*h*C*g/f/theta0*(Y[:,0] - Yc[:,0]) + 0.5*h*C*g/f/theta0*(Yn[:,0] - Ycent[:,0])
        Y[:,0] = Y[:,0] + 0.5*h*C*g/f/theta0*(Yc[:,1] - H*np.ones(Yc[:,1].size)/2.) + 0.5*h*C*g/f/theta0*(Ycent[:,1] - H*np.ones(Ycent[:,1].size)/2.)

        #bring back into bounding box
        Y = dens.to_fundamental_domain(Y)
        
    if add_data:
        return Y, w, energy, vgmax, KEmean, t
    else:
        return Y, w
