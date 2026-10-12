#!/usr/bin/env python3
"""Ajoute ou remet en forme les liens de navigation des chapitres.

    navigation.py [--verifier]

Chaque chapitre reçoit, en tête et en pied, une ligne de navigation vers le
chapitre précédent, le sommaire (le Readme) et le chapitre suivant :

    [← Chapitre précédent](01-intro.md) · [Sommaire](Readme.md) · [Chapitre suivant →](03-suite.md)

Le premier chapitre n'a pas de lien « précédent », le dernier pas de lien
« suivant ». Les chapitres sont ceux du workflow Documents : les fichiers `.md`
de la racine dont le nom commence par un numéro ou par une lettre suivi d'un
séparateur, dans l'ordre naturel de leurs noms.

Une ligne de navigation existante — rien que des liens vers des fichiers `.md`,
séparés par « · », dont l'un mène au sommaire ou à un chapitre — est réécrite
dans la forme ci-dessus, ce qui corrige au passage des liens périmés par
l'insertion, le renommage ou la suppression d'un chapitre. Le reste du fichier
n'est pas touché.

Lancé à chaque push par le workflow « Navigation », qui commite le résultat.
Avec --verifier, rien n'est modifié : le code de sortie vaut 1 si un chapitre
est à reprendre.
"""

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import quote, unquote

# Même règle que l'inventaire du workflow Documents.
CHAPITRE = re.compile(r"^([0-9]+|[A-Za-z])[-._ ]")
LIEN = re.compile(r"\[([^\]]*)\]\(\s*([^)\s]+)\s*\)")
CLOTURE = re.compile(r"^\s*(```|~~~)")


def ordre_naturel(nom):
    """Clé de tri qui range « 10-… » après « 9-… », comme `sort -V`."""
    return [int(morceau) if morceau.isdigit() else morceau for morceau in re.split(r"(\d+)", nom)]


def ligne_navigation(precedent, sommaire, suivant):
    # Les noms sont encodés : un lien dont la cible contient une espace n'est
    # pas reconnu, ni par GitHub ni par la conversion en liens internes du PDF.
    parties = []
    if precedent:
        parties.append(f"[← Chapitre précédent]({quote(precedent)})")
    parties.append(f"[Sommaire]({quote(sommaire)})")
    if suivant:
        parties.append(f"[Chapitre suivant →]({quote(suivant)})")
    return " · ".join(parties)


def est_navigation(ligne):
    liens = list(LIEN.finditer(ligne))
    if not liens or LIEN.sub("", ligne).replace("·", "").strip():
        return False
    for lien in liens:
        cible = unquote(lien.group(2).split("#")[0])
        if re.match(r"[a-z][a-z0-9+.-]*:", cible, re.I) or not cible.lower().endswith(".md"):
            return False
    return any(re.search(r"sommaire|chapitre", lien.group(1), re.I) for lien in liens)


def mettre_en_forme(texte, navigation):
    lignes = texte.splitlines()
    if not any(l.strip() and not est_navigation(l) for l in lignes):
        return texte  # chapitre vide : rien à relier

    # En tête : la zone qui précède le titre de niveau 1, hors bloc de code. Sans
    # titre, la seule première ligne non vide.
    titre, cloture = None, False
    for i, ligne in enumerate(lignes):
        if CLOTURE.match(ligne):
            cloture = not cloture
        elif not cloture and re.match(r"#\s", ligne):
            titre = i
            break
    premiere = next(i for i, l in enumerate(lignes) if l.strip())
    zone = range(titre) if titre is not None else range(premiere, premiere + 1)
    tete = next((i for i in zone if est_navigation(lignes[i])), None)
    if tete is None:
        lignes[0:0] = [navigation, ""]
        tete = 0
    else:
        lignes[tete] = navigation
    # Une ligne vide, une seule, entre la navigation et ce qui suit.
    suite = tete + 1
    while suite < len(lignes) and not lignes[suite].strip():
        del lignes[suite]
    lignes.insert(suite, "")

    # En pied : un filet, puis la navigation, en dernière ligne. Un filet ou
    # une navigation déjà en place sont remplacés, pas doublés.
    while lignes and not lignes[-1].strip():
        lignes.pop()
    if len(lignes) - 1 > tete and est_navigation(lignes[-1]):
        lignes.pop()
        while lignes and not lignes[-1].strip():
            lignes.pop()
    if len(lignes) - 1 > tete and lignes[-1].strip() == "---":
        lignes.pop()
        while lignes and not lignes[-1].strip():
            lignes.pop()
    lignes += ["", "---", "", navigation]

    fin = "\r\n" if "\r\n" in texte else "\n"
    return fin.join(lignes) + fin


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    analyseur = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    analyseur.add_argument("--verifier", action="store_true", help="ne modifie rien, signale les chapitres à reprendre")
    arguments = analyseur.parse_args()

    racine = Path(".")
    # Les noms tels qu'écrits sur le disque : sous Windows ou macOS, dont le
    # système de fichiers ignore la casse, tester « README.md » trouverait
    # aussi « Readme.md », et le lien porterait la mauvaise graphie.
    fichiers = {f.name for f in racine.iterdir() if f.is_file()}
    sommaire = next((n for n in ("README.md", "Readme.md", "readme.md") if n in fichiers), None)
    if sommaire is None:
        print("::error::Aucun Readme à la racine : il n'y a pas de sommaire vers lequel renvoyer.")
        return 1
    chapitres = sorted((n for n in fichiers
                        if n.endswith(".md") and CHAPITRE.match(n) and n != sommaire),
                       key=ordre_naturel)
    if not chapitres:
        print("Aucun chapitre : pas de navigation à poser.")
        return 0

    a_reprendre = []
    for i, nom in enumerate(chapitres):
        navigation = ligne_navigation(chapitres[i - 1] if i > 0 else None, sommaire,
                                      chapitres[i + 1] if i + 1 < len(chapitres) else None)
        chemin = racine / nom
        # newline="" : les fins de ligne du fichier sont conservées telles quelles.
        with open(chemin, encoding="utf-8", newline="") as f:
            texte = f.read()
        nouveau = mettre_en_forme(texte, navigation)
        if nouveau == texte:
            continue
        a_reprendre.append(nom)
        if arguments.verifier:
            print(f"::error file={nom},line=1::Liens de navigation absents ou périmés.")
        else:
            with open(chemin, "w", encoding="utf-8", newline="") as f:
                f.write(nouveau)
            print(f"Navigation mise à jour : {nom}")

    if not a_reprendre:
        print(f"Navigation à jour ({len(chapitres)} chapitre(s)).")
    return 1 if arguments.verifier and a_reprendre else 0


if __name__ == "__main__":
    sys.exit(main())
