"""
Generates data for numerical experiments in the thesis

Power law network: methodology is inspired by "The joint graphical lasso for inverse covariance estimation across
multiple classes" from Danaher et al.

"""

import numpy as np
import networkx as nx

#%%
def power_law_network(p=100, M=10):
    
    L = int(p/M)
    assert M*L == p
    
    A = np.zeros((p,p))
    Sigma = np.zeros((p,p))
    
    for m in np.arange(M):
    
        G_m = nx.generators.random_graphs.random_powerlaw_tree(n = L, gamma = 3, tries = 200)
        A_m = nx.to_numpy_array(G_m)
        
        # generate random numbers for the nonzero entries
        B1 = np.random.uniform(low = .1, high = .4, size = (L,L))
        B2 = np.random.choice(a = [-1,1], p=[.5, .5], size = (L,L))
        
        A_m = A_m * (B1*B2)
        
        A[m*L:(m+1)*L, m*L:(m+1)*L] = A_m
    
    
    row_sum_od = 1.5 * abs(A).sum(axis = 1)
    # broadcasting in order to divide ROW-wise
    A = A/ row_sum_od[:,np.newaxis]
    
    # A has 0 on diagonal, fill with 1s
    A = A + np.eye(p)
    assert all(np.diag(A)==1), "Expected 1s on diagonal"
    
    A = .5 * (A + A.T)
    
    
    D,_ = np.linalg.eig(A)
    assert D.min() > 0, "generated matrix A is not positive definite"
    
    
    Ainv = np.linalg.inv(A)
    
    for i in np.arange(p):
        for j in np.arange(p):
            
            if i == j:
                Sigma[i,j] = Ainv[i,j]/np.sqrt(Ainv[i,i] * Ainv[j,j])
            else:
                Sigma[i,j] = 0.6 * Ainv[i,j]/np.sqrt(Ainv[i,i] * Ainv[j,j])
    
    
    assert abs(Sigma.T - Sigma).max() <= 1e-8
    D,_ = np.linalg.eig(Sigma)
    assert D.min() > 0, "generated matrix Sigma is not positive definite"
         
    #Theta = np.linalg.inv(Sigma)
    
    return Sigma

def time_varying_power_network(p=100, K=10, M=10):
    """
    generates a power law network. The first block disappears at half-time, while the second block appears 
    p: dimension
    K: number of instances/time-stamps
    M: number of sublocks in each instance
    """  
    Sigma = np.zeros((K,p,p))
    
    L = int(p/M)
    assert M*L == p
    
    Sigma_0 = power_law_network(p = p, M = M)
    
    for k in np.arange(K):
        
        Sigma_k = Sigma_0.copy()    
        if k <= K/2:   
            Sigma_k[L:2*L, L:2*L] = np.eye(L)
        else:
            Sigma_k[0:L, 0:L] = np.eye(L)
            
        Sigma[k,:,:] = Sigma_k
        
    Theta = np.linalg.inv(Sigma)
        
    return Sigma, Theta
    
def group_power_network(p=100, K=10, M=10):
    """
    generates a power law network. In each single network one block disappears (randomly)
    p: dimension
    K: number of instances/time-stamps
    M: number of sublocks in each instance
    """  
    Sigma = np.zeros((K,p,p))
    
    L = int(p/M)
    assert M*L == p
    
    Sigma_0 = power_law_network(p = p, M = M)
    # contains the number of the block disappearing for each k=1,..,K
    block = np.random.randint(M, size = K)
    
    for k in np.arange(K):
        
        Sigma_k = Sigma_0.copy()           
        Sigma_k[block[k]*L : (block[k]+1)*L, block[k]*L : (block[k]+1)*L] = np.eye(L)
        Sigma[k,:,:] = Sigma_k
        
    Theta = np.linalg.inv(Sigma)
        
    return Sigma, Theta    

#%%

from evaluation import draw_group_graph

Sigma, Theta   = group_power_network(p=100, K=10, M=10)

fig = draw_group_graph(Theta)

# calc adjacency matrix
#adjA = (Theta != 0).astype(int)
#
#G = nx.from_numpy_array(adjA)
#nx.draw(G)



