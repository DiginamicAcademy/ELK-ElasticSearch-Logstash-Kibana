"""Mini-défi — moteur de recherche d'offres en ligne de commande.

Attendu :
  python search.py "développeur python"
  python search.py "données spark" --ville Lyon --contrat CDI --salaire-min 45000
  python search.py "kubernetes" --autour "43.6108,3.8767"--rayon 50km --teletravail partiel
"""

from __future__ import annotations

import argparse

from es_client import INDEX, get_client


def construire_requete(args: argparse.Namespace) -> dict:
    """TODO : requête bool
    - must   : multi_match sur titre (x3), competences.texte (x2), description, tolérant aux fautes
    - filter : ville, contrat, teletravail (term), salaire_max >= --salaire-min (range),
               distance autour d'un point (geo_distance) si --autour est fourni
    """
    raise NotImplementedError


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("texte")
    p.add_argument("--ville")
    p.add_argument("--contrat", choices=["CDI", "CDD", "Alternance", "Freelance", "Stage"])
    p.add_argument("--teletravail", choices=["aucun", "partiel", "total"])
    p.add_argument("--salaire-min", type=int)
    p.add_argument("--autour", help="lat,lon")
    p.add_argument("--rayon", default="30km")
    p.add_argument("--page", type=int, default=1)
    p.add_argument("--taille", type=int, default=10)
    args = p.parse_args()

    es = get_client()
    # TODO : appeler es.search avec la requête, la pagination (from_, size), un highlight sur
    # description et trois facettes (aggs terms) : ville, contrat, compétences.
    # Afficher : total, puis pour chaque résultat score, titre, entreprise, ville, contrat, salaire,
    # l'extrait surligné, et enfin les facettes.


if __name__ == "__main__":
    main()
