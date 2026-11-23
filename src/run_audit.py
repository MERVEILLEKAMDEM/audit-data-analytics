"""Lance la campagne d'audit et produit le rapport (CSV, graphiques, HTML)."""
from datetime import date
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

import audit_tests as at
from generate_data import generer

RACINE = Path(__file__).resolve().parents[1]
DATA, RES = RACINE / "data", RACINE / "results"
FIG = RES / "figures"
BLEU, ROUGE, GRIS = "#1f4e79", "#c0392b", "#95a5a6"


def charger():
    if not (DATA / "contrats.csv").exists():
        generer(DATA)
    c = pd.read_csv(DATA / "contrats.csv", parse_dates=["date_effet"])
    s = pd.read_csv(DATA / "sinistres.csv", parse_dates=["date_declaration"])
    p = pd.read_csv(DATA / "paiements.csv", parse_dates=["date_paiement"])
    return c, s, p


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    contrats, sinistres, paiements = charger()
    resultats = at.lancer_tous(contrats, sinistres, paiements)
    bf = at.benford(paiements["montant_paye"])

    # --- Export des anomalies -------------------------------------------------
    lignes = []
    with pd.ExcelWriter(RES / "anomalies.xlsx") if _has_openpyxl() else _Null() as xw:
        for nom, df in resultats.items():
            lignes.append({"controle": nom, "anomalies": len(df)})
            if xw is not None:
                df.to_excel(xw, sheet_name=nom[:31], index=False)
    synthese = pd.DataFrame(lignes)
    synthese.to_csv(RES / "synthese.csv", index=False)
    pd.concat([d[[c for c in d.columns if c.startswith("id_")][:1] + ["motif"]]
               .rename(columns=lambda x: "identifiant" if x.startswith("id_") else x)
               for d in resultats.values()]).to_csv(RES / "anomalies.csv", index=False)

    # --- Graphiques -----------------------------------------------------------
    fig, ax = plt.subplots(figsize=(8, 4))
    s = synthese.sort_values("anomalies")
    ax.barh(s["controle"], s["anomalies"], color=BLEU)
    for i, v in enumerate(s["anomalies"]):
        ax.text(v + 0.3, i, str(v), va="center")
    ax.set_title("Anomalies détectées par contrôle")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(FIG / "anomalies_par_controle.png", dpi=150); plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(bf.index, bf["observe"], color=BLEU, label="Observé")
    ax.plot(bf.index, bf["benford"], color=ROUGE, marker="o", label="Loi de Benford")
    ax.set_xticks(range(1, 10)); ax.set_xlabel("Premier chiffre"); ax.set_ylabel("Fréquence")
    ax.set_title(f"Test de Benford sur les paiements (MAD = {bf.attrs['mad']:.4f})")
    ax.legend(frameon=False); ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(FIG / "benford.png", dpi=150); plt.close(fig)

    pa = at.primes_atypiques(contrats)
    fig, ax = plt.subplots(figsize=(8, 4))
    for i, (prod, g) in enumerate(contrats.groupby("produit")):
        ax.scatter([i] * len(g), g["prime_annuelle"], s=6, alpha=.25, color=GRIS)
        o = pa[pa["produit"] == prod]
        ax.scatter([i] * len(o), o["prime_annuelle"], s=22, color=ROUGE)
    ax.set_yscale("log"); ax.set_xticks(range(contrats["produit"].nunique()))
    ax.set_xticklabels(sorted(contrats["produit"].unique()))
    ax.set_title("Primes annuelles par produit (rouge = atypiques)")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(FIG / "primes_atypiques.png", dpi=150); plt.close(fig)

    # --- Rapport HTML ---------------------------------------------------------
    total = int(synthese["anomalies"].sum())
    montant_risque = float(resultats["Paiements sans validation"]["montant_paye"].sum()
                           + resultats["Séparation des tâches"]["montant_paye"].sum())
    rows = "".join(f"<tr><td>{r.controle}</td><td>{r.anomalies}</td></tr>" for r in synthese.itertuples())
    html = f"""<!DOCTYPE html><html lang="fr"><meta charset="utf-8">
<title>Rapport d'audit data</title>
<style>body{{font-family:Arial;max-width:900px;margin:40px auto;color:#222}}
h1{{color:{BLEU}}}table{{border-collapse:collapse}}td,th{{border:1px solid #ccc;padding:6px 12px}}
.kpi{{display:inline-block;margin-right:30px;font-size:28px;color:{BLEU}}}.kpi small{{display:block;font-size:13px;color:#666}}</style>
<h1>Rapport d'audit data – Assurance vie (données fictives)</h1>
<p>Généré le {date.today():%d/%m/%Y} sur {fr(len(contrats))} contrats, {fr(len(sinistres))} sinistres et {fr(len(paiements))} paiements.</p>
<div class="kpi">{total}<small>anomalies</small></div>
<div class="kpi">{fr(montant_risque)} €<small>payés sans contrôle 4 yeux</small></div>
<div class="kpi">{bf.attrs['conformite']}<small>test de Benford</small></div>
<h2>Synthèse des contrôles</h2><table><tr><th>Contrôle</th><th>Anomalies</th></tr>{rows}</table>
<img src="figures/anomalies_par_controle.png" width="100%">
<img src="figures/primes_atypiques.png" width="100%">
<img src="figures/benford.png" width="100%">
</html>"""
    (RES / "rapport_audit.html").write_text(html, encoding="utf-8")
    print(synthese.to_string(index=False))
    print(f"Benford : MAD={bf.attrs['mad']:.4f} -> {bf.attrs['conformite']}")
    print(f"Montant payé sans contrôle 4 yeux : {montant_risque:,.0f} €")


def fr(x):
    return f"{x:,.0f}".replace(",", "\u202f")


def _has_openpyxl():
    try:
        import openpyxl  # noqa: F401
        return True
    except ImportError:
        return False


class _Null:
    def __enter__(self): return None
    def __exit__(self, *a): return False


if __name__ == "__main__":
    main()
