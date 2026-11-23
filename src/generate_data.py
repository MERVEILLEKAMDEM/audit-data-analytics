"""Génère un jeu de données fictif d'assurance vie (contrats, sinistres, paiements).

Les données sont 100 % synthétiques. Des anomalies sont injectées volontairement
pour vérifier que les tests d'audit les retrouvent.
"""
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
N_CONTRATS = 5000
PRODUITS = {
    "Epargne": (25_000, 0.9),
    "Retraite": (40_000, 0.8),
    "Prevoyance": (8_000, 0.6),
    "Obseques": (4_000, 0.4),
}
AGENCES = ["Paris", "Lyon", "Lille", "Nantes", "Bordeaux", "Marseille", "Toulouse"]
UTILISATEURS = [f"U{i:03d}" for i in range(1, 26)]


def generer(dossier: Path = Path(__file__).resolve().parents[1] / "data") -> dict:
    rng = np.random.default_rng(SEED)
    dossier.mkdir(parents=True, exist_ok=True)

    # ---- Contrats -----------------------------------------------------------
    produits = rng.choice(list(PRODUITS), N_CONTRATS, p=[0.45, 0.25, 0.2, 0.1])
    debut = pd.Timestamp("2019-01-01") + pd.to_timedelta(rng.integers(0, 5 * 365, N_CONTRATS), "D")
    primes = [rng.lognormal(np.log(PRODUITS[p][0]), PRODUITS[p][1]) for p in produits]
    contrats = pd.DataFrame({
        "id_contrat": [f"C{i:06d}" for i in range(N_CONTRATS)],
        "id_client": [f"CL{x:05d}" for x in rng.integers(0, 4200, N_CONTRATS)],
        "produit": produits,
        "agence": rng.choice(AGENCES, N_CONTRATS),
        "date_effet": debut,
        "prime_annuelle": np.round(primes, 2),
    })

    # ---- Sinistres / rachats -------------------------------------------------
    n_sin = 1800
    idx = rng.integers(0, N_CONTRATS, n_sin)
    delai = pd.to_timedelta(rng.integers(30, 1500, n_sin), "D")
    sinistres = pd.DataFrame({
        "id_sinistre": [f"S{i:06d}" for i in range(n_sin)],
        "id_contrat": contrats.loc[idx, "id_contrat"].values,
        "date_declaration": contrats.loc[idx, "date_effet"].values + delai,
        "montant_demande": np.round(contrats.loc[idx, "prime_annuelle"].values * rng.uniform(0.2, 3, n_sin), 2),
    })

    # ---- Paiements -----------------------------------------------------------
    n_pay = 1500
    sel = rng.choice(n_sin, n_pay, replace=False)
    createur = rng.choice(UTILISATEURS, n_pay)
    valideur = np.array([rng.choice([u for u in UTILISATEURS if u != c]) for c in createur])
    paiements = pd.DataFrame({
        "id_paiement": [f"P{i:06d}" for i in range(n_pay)],
        "id_sinistre": sinistres.loc[sel, "id_sinistre"].values,
        "montant_paye": sinistres.loc[sel, "montant_demande"].values * rng.uniform(0.9, 1.0, n_pay),
        "date_paiement": sinistres.loc[sel, "date_declaration"].values + pd.to_timedelta(rng.integers(5, 90, n_pay), "D"),
        "cree_par": createur,
        "valide_par": valideur,
    })
    paiements["montant_paye"] = paiements["montant_paye"].round(2)

    # ---- Injection d'anomalies (pour valider les contrôles) ------------------
    injectees = {}
    # 1. Doublons de contrats (même client, produit, date et prime)
    dup = contrats.sample(12, random_state=SEED).copy()
    dup["id_contrat"] = [f"C9{i:05d}" for i in range(len(dup))]
    contrats = pd.concat([contrats, dup], ignore_index=True)
    injectees["doublons_contrats"] = len(dup)
    # 2. Primes anormalement élevées
    out = rng.choice(N_CONTRATS, 15, replace=False)
    contrats.loc[out, "prime_annuelle"] *= 40
    injectees["primes_atypiques"] = len(out)
    # 3. Sinistres déclarés avant la date d'effet du contrat
    av = rng.choice(n_sin, 20, replace=False)
    eff = sinistres.loc[av, "id_contrat"].map(contrats.drop_duplicates("id_contrat").set_index("id_contrat")["date_effet"])
    sinistres.loc[av, "date_declaration"] = eff.values - pd.to_timedelta(rng.integers(10, 200, len(av)), "D")
    injectees["sinistres_avant_effet"] = len(av)
    # 4. Paiements sans validation
    sv = rng.choice(n_pay, 18, replace=False)
    paiements.loc[sv, "valide_par"] = None
    # 5. Séparation des tâches : même personne crée et valide
    sod = rng.choice(np.setdiff1d(np.arange(n_pay), sv), 10, replace=False)
    paiements.loc[sod, "valide_par"] = paiements.loc[sod, "cree_par"]
    injectees["paiements_sans_validation"] = len(sv)
    injectees["separation_taches"] = len(sod)
    # 6. Paiement supérieur au montant demandé
    sup = rng.choice(np.setdiff1d(np.arange(n_pay), np.r_[sv, sod]), 8, replace=False)
    paiements.loc[sup, "montant_paye"] = (paiements.loc[sup, "montant_paye"] * 1.6).round(2)
    injectees["paiement_superieur_demande"] = len(sup)

    contrats.to_csv(dossier / "contrats.csv", index=False)
    sinistres.to_csv(dossier / "sinistres.csv", index=False)
    paiements.to_csv(dossier / "paiements.csv", index=False)
    return injectees


if __name__ == "__main__":
    print("Anomalies injectées :", generer())
