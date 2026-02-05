# -*- coding: utf-8 -*-
"""
Created on Wed Feb  4 22:19:45 2026

@author: evanc
"""

import numpy as np
from scipy.stats import skellam

#Paramètres bidons
capacity = 8     # capacité de la station
lambda1 = 20      # retours moyens sur un intervalle de temp dt
lambda2 = 40     # demandes moyenne sur un intervalle de temp dt
beta_empty = 3.0  # pénalité rupture (si on veut on peut mettre la rupture plus relou que le fait que ce soit plein)
beta_full = 1.0   # pénalité station pleine
support = 25      # support de la loi de Skellam (valeur possible de la variable aléatoire à laquelle on met des limites pour pas avoir a calculer entre -inf et +inf)



# fonction qui renvoie la penalite
def penalty(b, capacity, beta_empty, beta_full):
    if b < 0:
        return -b * beta_empty
    elif b > capacity:
        return (b - capacity) * beta_full
    else:
        return 0.0



def expected_penalty(b_t):
    delta = np.arange(-support, support + 1)

    probs = skellam.pmf(delta, lambda1, lambda2) #lambda1 et lambda2, deux paramètre de lois de poisson
    stocks = b_t + delta

    Z = 0.0
    for b, p in zip(stocks, probs): #zip pour parcourir deux tableaux en meme temps
        print(b)
        Z += p * penalty(b, capacity, beta_empty, beta_full) #revoir cette ligne peut-etre, j'ai un doute si elle suit bien la loi de Skellam

    return Z




#dico des penalites
Z_values = {}
for b in range(capacity + 1):
    Z_values[b] = expected_penalty(b)

#stock optimal
b_star = min(Z_values, key=Z_values.get)




#tableau récap
print("===== TABLEAU DES PÉNALITÉS =====")
for b in range(capacity + 1):
    marker = " <--- OPTIMAL" if b == b_star else ""
    print(f"b = {b:2d}  |  Z = {Z_values[b]:.4f}{marker}")
