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
