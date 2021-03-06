"""
author: Fabian Schaipp

Sigma denotes the covariance matrix, Theta the precision matrix
"""
from time import time
import numpy as np

from sklearn.covariance import GraphicalLasso

from gglasso.solver.ppdna_solver import PPDNA, warmPPDNA
from gglasso.solver.admm_solver import ADMM_MGL
from gglasso.helper.data_generation import time_varying_power_network, sample_covariance_matrix
from gglasso.helper.experiment_helper import get_K_identity, lambda_grid, discovery_rate, error
from gglasso.helper.experiment_helper import plot_evolution, plot_deviation, surface_plot, plot_fpr_tpr, multiple_heatmap_animation, single_heatmap_animation
from gglasso.helper.model_selection import aic, ebic

from regain.covariance import LatentTimeGraphicalLasso, TimeGraphicalLasso

p = 100
K = 10
N = 5000
M = 5
L = int(p/M)

reg = 'FGL'

Sigma, Theta = time_varying_power_network(p, K, M)
#np.linalg.norm(np.eye(p) - Sigma@Theta)/np.linalg.norm(np.eye(p))

#single_heatmap_animation(Theta)

S, sample = sample_covariance_matrix(Sigma, N)
S_train, sample_train = sample_covariance_matrix(Sigma, N)
Sinv = np.linalg.pinv(S, hermitian = True)


results = {}
results['truth'] = {'Theta' : Theta}

#%%
# grid search for best lambda values with warm starts
L1, L2, _ = lambda_grid(num1 = 10, num2 = 5, reg = reg)
grid1 = L1.shape[0]; grid2 = L2.shape[1]

ERR = np.zeros((grid1, grid2))
FPR = np.zeros((grid1, grid2))
TPR = np.zeros((grid1, grid2))
DFPR = np.zeros((grid1, grid2))
DTPR = np.zeros((grid1, grid2))
AIC = np.zeros((grid1, grid2))
BIC = np.zeros((grid1, grid2))

Omega_0 = get_K_identity(K,p)
Theta_0 = get_K_identity(K,p)

for g1 in np.arange(grid1):
    for g2 in np.arange(grid2):
        lambda1 = L1[g1,g2]
        lambda2 = L2[g1,g2]
              
        sol, info = warmPPDNA(S_train, lambda1, lambda2, reg, Omega_0, Theta_0 = Theta_0, eps = 1e-3, verbose = False, measure = False)
        Theta_sol = sol['Theta']
        Omega_sol = sol['Omega']
        
        # warm start
        Omega_0 = Omega_sol.copy()
        Theta_0 = Theta_sol.copy()
        
        TPR[g1,g2] = discovery_rate(Theta_sol, Theta)['TPR']
        FPR[g1,g2] = discovery_rate(Theta_sol, Theta)['FPR']
        DTPR[g1,g2] = discovery_rate(Theta_sol, Theta)['TPR_DIFF']
        DFPR[g1,g2] = discovery_rate(Theta_sol, Theta)['FPR_DIFF']
        ERR[g1,g2] = error(Theta_sol, Theta)
        AIC[g1,g2] = aic(S_train, Theta_sol, N)
        BIC[g1,g2] = ebic(S_train, Theta_sol, N, gamma = 0.1)

# get optimal lambda
ix= np.unravel_index(np.nanargmin(BIC), BIC.shape)
ix2= np.unravel_index(np.nanargmin(AIC), AIC.shape)
lambda1 = L1[ix]
lambda2 = L2[ix]

print("Optimal lambda values: (l1,l2) = ", (lambda1,lambda2))
plot_fpr_tpr(FPR.T, TPR.T,  ix[::-1], ix2[::-1])

#%%
# solve with QUIC/single Glasso
#from inverse_covariance import QuicGraphicalLasso
#quic = QuicGraphicalLasso(lam = 1.5*lambda1, tol = 1e-6)

singleGL = GraphicalLasso(alpha = 1.5*lambda1, tol = 1e-6, max_iter = 200, verbose = True)

res = np.zeros((K,p,p))
for k in np.arange(K):
    #model = quic.fit(S[k,:,:], verbose = 1)
    model = singleGL.fit(sample[k,:,:].T)
    
    res[k,:,:] = model.precision_

results['GLASSO'] = {'Theta' : res}

#%%
# solve with PPDNA
Omega_0 = results.get('GLASSO').get('Theta')
Theta_0 = Omega_0.copy()
X_0 = np.zeros((K,p,p))

start = time()
sol, info = warmPPDNA(S, lambda1, lambda2, reg, Omega_0, Theta_0 = Theta_0, X_0 = X_0, eps = 5e-4 , verbose = True, measure = True)
end = time()

print(f"Running time for PPDNA was {end-start} seconds")
results['PPDNA'] = {'Theta' : sol['Theta']}

#%%
# solve with general ADMM
start = time()
sol, info = ADMM_MGL(S, lambda1, lambda2, reg, Omega_0, Theta_0 = Theta_0, X_0 = X_0, rho = 1, max_iter = 100, \
                                                        eps_admm = 5e-4, verbose = True, measure = True)
end = time()

print(f"Running time for ADMM was {end-start} seconds")

results['ADMM'] = {'Theta' : sol['Theta']}

#%%
# solve with ragin (LTGL)

start = time()
alpha = N*lambda1
beta = N*lambda2 
ltgl = TimeGraphicalLasso(alpha = alpha, beta = beta , psi = 'l1', \
                          rho = 1., tol = 5e-4, rtol = 5e-4,  max_iter = 2000, verbose = True)
ltgl = ltgl.fit(sample.transpose(0,2,1))
end = time()

print(f"Running time for LTGL was {end-start}  seconds")

results['LTGL'] = {'Theta' : ltgl.precision_}

#%%
# plotting
Theta_admm = results.get('ADMM').get('Theta')
Theta_ppdna = results.get('PPDNA').get('Theta')
Theta_ltgl = results.get('LTGL').get('Theta')
Theta_glasso = results.get('GLASSO').get('Theta')


print(np.linalg.norm(Theta_ltgl - Theta_admm)/ np.linalg.norm(Theta_admm))
print(np.linalg.norm(Theta_ppdna - Theta_admm)/ np.linalg.norm(Theta_admm))


save = True

surface_plot(L1, L2, BIC, name = 'eBIC', save = save)

plot_evolution(results, block = 0, L = L, save = save)

plot_evolution(results, block = 2, L = L, save = save)

del results['ADMM']

plot_deviation(results, save = save)


# animate truth and solution
single_heatmap_animation(Theta_glasso, method = 'GLASSO', save = False)
multiple_heatmap_animation(Theta, results, save = False)



