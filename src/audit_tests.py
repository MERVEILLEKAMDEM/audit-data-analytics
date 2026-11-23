"""Bibliothèque de tests d'audit sur données.

Chaque test prend des DataFrames et renvoie les lignes en anomalie avec une
colonne ``motif`` qui explique pourquoi la ligne est remontée.
"""
import numpy as np
import pandas as pd


def doublons_contrats(contrats: pd.DataFrame) -> pd.DataFrame:
    """Contrats identiques (client, produit, date d'effet, prime) sous deux numéros."""
    cles = ["id_client", "produit", "date_effet", "prime_annuelle"]
    res = contrats[contrats.duplicated(cles, keep=False)].sort_values(cles)
    return res.assign(motif="Contrat en double (même client, produit, date et prime)")


def primes_atypiques(contrats: pd.DataFrame, seuil: float = 3.5) -> pd.DataFrame:
    """Primes hors norme par produit, via le z-score robuste (médiane / MAD) sur le log."""
    df = contrats.copy()
    df["log_prime"] = np.log(df["prime_annuelle"])
    grp = df.groupby("produit")["log_prime"]
    med = grp.transform("median")
    mad = grp.transform(lambda s: (s - s.median()).abs().median())
    df["z_robuste"] = 0.6745 * (df["log_prime"] - med) / mad
    res = df[df["z_robuste"].abs() > seuil].drop(columns="log_prime")
    return res.assign(motif="Prime atypique pour ce produit (z robuste > %.1f)" % seuil)


def sinistres_avant_effet(sinistres: pd.DataFrame, contrats: pd.DataFrame) -> pd.DataFrame:
    """Sinistres déclarés avant la date d'effet du contrat."""
    eff = contrats.drop_duplicates("id_contrat")[["id_contrat", "date_effet"]]
    df = sinistres.merge(eff, on="id_contrat", how="left")
    res = df[df["date_declaration"] < df["date_effet"]]
    return res.assign(motif="Sinistre déclaré avant la date d'effet du contrat")


def paiements_sans_validation(paiements: pd.DataFrame) -> pd.DataFrame:
    res = paiements[paiements["valide_par"].isna()]
    return res.assign(motif="Paiement émis sans validation")


def separation_des_taches(paiements: pd.DataFrame) -> pd.DataFrame:
    res = paiements[paiements["cree_par"] == paiements["valide_par"]]
    return res.assign(motif="Même utilisateur a créé et validé le paiement")


def paiement_superieur_demande(paiements: pd.DataFrame, sinistres: pd.DataFrame) -> pd.DataFrame:
    df = paiements.merge(sinistres[["id_sinistre", "montant_demande"]], on="id_sinistre")
    res = df[df["montant_paye"] > df["montant_demande"] * 1.0001]
    return res.assign(motif="Montant payé supérieur au montant demandé")


def benford(montants: pd.Series) -> pd.DataFrame:
    """Compare la distribution du premier chiffre à la loi de Benford."""
    m = montants[montants >= 1].astype(str).str.lstrip("0.").str[0].astype(int)
    obs = m.value_counts(normalize=True).reindex(range(1, 10), fill_value=0)
    theo = pd.Series(np.log10(1 + 1 / np.arange(1, 10)), index=range(1, 10))
    mad = float((obs - theo).abs().mean())
    out = pd.DataFrame({"observe": obs, "benford": theo, "ecart": obs - theo})
    out.attrs["mad"] = mad
    # Seuils de Nigrini pour le premier chiffre
    out.attrs["conformite"] = (
        "Conformité forte" if mad < 0.006 else
        "Conformité acceptable" if mad < 0.012 else
        "Conformité marginale" if mad < 0.015 else "Non conforme"
    )
    return out


def lancer_tous(contrats, sinistres, paiements) -> dict:
    return {
        "Doublons de contrats": doublons_contrats(contrats),
        "Primes atypiques": primes_atypiques(contrats),
        "Sinistres avant date d'effet": sinistres_avant_effet(sinistres, contrats),
        "Paiements sans validation": paiements_sans_validation(paiements),
        "Séparation des tâches": separation_des_taches(paiements),
        "Paiement > montant demandé": paiement_superieur_demande(paiements, sinistres),
    }
