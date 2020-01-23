"""
author: Fabian Schaipp
"""

import numpy as np

from .basic_linalg import Sdot, adjacency_matrix
from .experiment_helper import mean_sparsity

from .experiment_helper import get_K_identity as id_array
from .ext_admm_helper import get_K_identity as id_dict

def lambda_parametrizer(l1 = 0.05, w2 = 0.5):
    """transforms given l1 and w2 into the respective l2"""
    a = 1/np.sqrt(2)
    l2 = (w2*l1)/(a*(1-w2))

    return l2

def lambda_grid(num1 = 5, num2 = 2, reg = 'GGL'):
    """
    num1: number of grid point for lambda 1
    num2: number of grid point for lambda 2
    reg: grid for GGL or FGL (interpretation changes)
    idea: the grid goes from higher to smaller values when going down/right
    """   
    if reg == 'GGL':
        l1 = 5*np.logspace(start = -1, stop = -2, num = num1, base = 10)
        w2 = np.linspace(0.5, 0.2, num2)
        l1grid, w2grid = np.meshgrid(l1,w2)
        L2 = lambda_parametrizer(l1grid, w2grid)
        L1 = l1grid.copy()
    elif reg == 'FGL':
        l2 = 2*np.logspace(start = -1, stop = -3, num = num2, base = 10)
        l1 = 2*np.logspace(start = -1, stop = -3, num = num1, base = 10)
        L1, L2 = np.meshgrid(l1,l2)
        w2 = None
        
    return L1.squeeze(), L2.squeeze(), w2

def model_select(solver, S, N, p, reg, method, G = None, gridsize1 = 6, gridsize2 = 3):
    """
    method for doing model selection using grid search and AIC/eBIC
    gridsize1 = size of grid resp. to lambda1
    gridsize2 = size of grid resp. to lambda2
    """
    
    assert method in ['AIC', 'BIC']
    assert reg in ['FGL', 'GGL']
    L1, L2, W2 = lambda_grid(num1 = gridsize1, num2 = gridsize2, reg = reg)
    
    grid1 = L1.shape[0]; grid2 = L2.shape[1]
    assert grid1 == gridsize2
    assert grid2 == gridsize1
    AIC = np.zeros((grid1, grid2))
    AIC[:] = np.nan
    BIC = np.zeros((grid1, grid2))
    BIC[:] = np.nan
    SP = np.zeros((grid1, grid2))
    SP[:] = np.nan
    SKIP = np.zeros((grid1, grid2), dtype = bool)
    
    kwargs = {'reg': reg, 'S': S, 'eps_admm': 1e-3, 'verbose': True, 'measure': True}
    if type(S) == dict:
        K = len(S.keys())
        Omega_0 = id_dict(p)
        kwargs['G'] = G
    elif type(S) == np.ndarray:
        K = S.shape[0]
        Omega_0 = id_array(K,p)
        
    kwargs['Omega_0'] = Omega_0
    
    
    for g1 in np.arange(grid1):
        for g2 in np.arange(grid2):
            
            print("Current grid point: ", (L1[g1,g2],L2[g1,g2]) )
            if SKIP[g1,g2]:
                print("SKIP")
                continue
            kwargs['lambda1'] = L1[g1,g2]
            kwargs['lambda2'] = L2[g1,g2]

            sol, info = solver(**kwargs)
            Omega_sol = sol['Omega']
            Theta_sol = sol['Theta']
            
            if mean_sparsity(Theta_sol) >= 0.15:
                SKIP[g1:, g2:] = True
            
            # warm start
            Omega_0 = Omega_sol.copy()
            
            AIC[g1,g2] = aic(S, Theta_sol, N)
            BIC[g1,g2] = ebic(S, Theta_sol, N, gamma = 0.1)
            SP[g1,g2] = mean_sparsity(Theta_sol)
    
    # get optimal lambda
    if method == 'AIC':
        ix= np.unravel_index(np.nanargmin(AIC), AIC.shape)
    elif method == 'BIC':    
        ix= np.unravel_index(np.nanargmin(BIC), BIC.shape)
    return AIC, BIC, L1, L2, ix, SP, SKIP

def aic(S, Theta, N):
    """
    AIC information criterion after Danaher et al.
    excludes the diagonal
    """
    if type(S) == dict:
        aic = aic_dict(S, Theta, N)
    elif type(S) == np.ndarray:
        aic = aic_array(S, Theta, N)
    else:
        raise KeyError("Not a valid input type -- should be either dictionary or ndarray")
    
    return aic

def ebic(S, Theta, N, gamma = 0.5):
    """
    extended BIC after Drton et al.
    """
    if type(S) == dict:
        aic = ebic_dict(S, Theta, N, gamma)
    elif type(S) == np.ndarray:
        aic = ebic_array(S, Theta, N, gamma)
    else:
        raise KeyError("Not a valid input type -- should be either dictionary or ndarray")
    
    return aic

def aic_array(S,Theta, N):
    (K,p,p) = S.shape
    
    if type(N) == int:
        N = np.ones(K) * N
    
    A = adjacency_matrix(Theta , t = 1e-5)
    nonzero_count = A.sum(axis=(1,2))/2
    aic = 0
    for k in np.arange(K):
        aic += N[k]*Sdot(S[k,:,:], Theta[k,:,:]) - N[k]*np.log(np.linalg.det(Theta[k,:,:])) + 2*nonzero_count[k]
        
    return aic

def ebic_array(S, Theta, N, gamma):
    (K,p,p) = S.shape
    if type(N) == int:
        N = np.ones(K) * N
    
    A = adjacency_matrix(Theta , t = 1e-5)
    nonzero_count = A.sum(axis=(1,2))/2
    
    bic = 0
    for k in np.arange(K):
        bic += N[k]*Sdot(S[k,:,:], Theta[k,:,:]) - N[k]*np.log(np.linalg.det(Theta[k,:,:])) + nonzero_count[k] * (np.log(N[k])+ 4*np.log(p)*gamma)
    
    return bic


def ebic_dict(S, Theta, N, gamma):
    """
    S, Theta are dictionaries
    N is array of sample sizes
    """
    K = len(S.keys())
    bic = 0
    for k in np.arange(K):
        A = adjacency_matrix(Theta[k] , t = 1e-5)
        p = S[k].shape[0]
        bic += N[k]*Sdot(S[k], Theta[k]) - N[k]*np.log(np.linalg.det(Theta[k])) + A.sum()/2 * (np.log(N[k])+ 4*np.log(p)*gamma)
        
    return bic
        

def aic_dict(S, Theta, N):
    """
    S, Theta are dictionaries
    N is array of sample sizes
    """
    K = len(S.keys())
    aic = 0
    for k in np.arange(K):
        A = adjacency_matrix(Theta[k] , t = 1e-5)
        aic += N[k]*Sdot(S[k], Theta[k]) - N[k]*np.log(np.linalg.det(Theta[k])) + A.sum()
        
    return aic