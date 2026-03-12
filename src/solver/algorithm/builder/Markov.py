import numpy as np
from scipy.stats import skellam

"""embedded discrete Markov chain ?"""


capacity = 20

lambda_return = 5      #naissance
lambda_rent = 9         #mort

beta_empty = 2
beta_full = 1

support = 25
states = capacity + 1

# matrice de transition
P = np.zeros((states, states))

for i in range(states):
    deltas = np.arange(-support, support+1)
    probs = skellam.pmf(deltas, lambda_return, lambda_rent)
    for d, p in zip(deltas, probs):
        j = i + d
        if j < 0:
            j = 0
        if j > capacity:
            j = capacity
        P[i, j] += p


# fonction pénalité
def penalty(b):
    if b == 0:
        return beta_empty
    if b == capacity:
        return beta_full
    return 0


# pénalité attendue
Z = []

for i in range(states):
    expected = 0
    for j in range(states):
        expected += P[i, j] * penalty(j)
    Z.append(expected)


b_star = np.argmin(Z)


print("===== TABLEAU DES PÉNALITÉS =====")
print("=====        MARKOV         =====")
for b in range(capacity + 1):
    marker = " <--- OPTIMAL" if b == b_star else ""
    print(f"b = {b:2d}  |  Z = {Z[b]:.4f}{marker}")