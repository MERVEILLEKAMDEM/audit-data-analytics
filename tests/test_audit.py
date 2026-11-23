"""Vérifie que chaque contrôle retrouve toutes les anomalies injectées."""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import audit_tests as at  # noqa: E402
from generate_data import generer  # noqa: E402


@pytest.fixture(scope="module")
def donnees(tmp_path_factory):
    d = tmp_path_factory.mktemp("data")
    injectees = generer(d)
    c = pd.read_csv(d / "contrats.csv", parse_dates=["date_effet"])
    s = pd.read_csv(d / "sinistres.csv", parse_dates=["date_declaration"])
    p = pd.read_csv(d / "paiements.csv", parse_dates=["date_paiement"])
    return injectees, c, s, p


def test_doublons(donnees):
    inj, c, s, p = donnees
    assert len(at.doublons_contrats(c)) == 2 * inj["doublons_contrats"]


def test_sinistres_avant_effet(donnees):
    inj, c, s, p = donnees
    assert len(at.sinistres_avant_effet(s, c)) == inj["sinistres_avant_effet"]


def test_controles_paiements(donnees):
    inj, c, s, p = donnees
    assert len(at.paiements_sans_validation(p)) == inj["paiements_sans_validation"]
    assert len(at.separation_des_taches(p)) == inj["separation_taches"]
    assert len(at.paiement_superieur_demande(p, s)) == inj["paiement_superieur_demande"]


def test_primes_atypiques_rappel(donnees):
    inj, c, s, p = donnees
    assert len(at.primes_atypiques(c)) >= inj["primes_atypiques"]


def test_benford_theorique():
    bf = at.benford(pd.Series([10 ** (i / 1000) for i in range(1, 6000)]))
    assert bf.attrs["mad"] < 0.006


def test_isolation_forest_precis(donnees):
    """Sans règle écrite, les paiements signalés doivent être de vraies anomalies injectées."""
    inj, c, s, p = donnees
    ml = at.anomalies_ml(p, s, c)
    sur = set(at.paiement_superieur_demande(p, s)["id_paiement"])
    avant = set(at.sinistres_avant_effet(s, c)["id_sinistre"])
    connues = sur | set(p[p["id_sinistre"].isin(avant)]["id_paiement"])
    assert len(ml) > 0
    assert len(set(ml["id_paiement"]) & connues) / len(ml) >= 0.8
