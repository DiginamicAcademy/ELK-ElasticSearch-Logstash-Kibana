#!/usr/bin/env python3
"""Vérifie config.yaml : structure, valeurs, existence des fiches et blocs RNCP,
section credits et existence des comptes GitHub qu'elle cite.

    verifier.py [--hors-ligne]

Lancé à chaque push qui touche config.yaml (workflow « Vérifier »), et avant
toute copie vers la partie pédagogique du cours (workflow « Pédagogie ») : une
déclaration invalide ne quitte pas ce dépôt.

Chaque problème est signalé par une annotation GitHub (::error, ::warning), qui
reste lisible en local. Le code de sortie vaut 1 s'il y a au moins une erreur ;
un avertissement seul ne fait pas échouer.

Dépendance : PyYAML. En local, l'installer dans un répertoire jetable plutôt
que dans l'environnement Python de l'utilisateur :

    pip install --target <dossier-jetable> pyyaml
    PYTHONPATH=<dossier-jetable> python3 .github/scripts/verifier.py
"""

import argparse
import http.client
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

import yaml

FICHE_RNCP = "https://www.francecompetences.fr/recherche/rncp/{}/"
# Bornes de la section des compétences d'une fiche, relevées dans l'AGENTS.md
# de la partie pédagogique (§ 3.2). La page d'une fiche inexistante répond 200 :
# seule l'absence du marqueur la trahit.
DEBUT_COMPETENCES = "accordion-content--fcpt-certification--skills"
FIN_COMPETENCES = "Description des modalités"

erreurs = 0


def signaler(niveau, message, fichier=None, ligne=None):
    global erreurs
    if niveau == "error":
        erreurs += 1
    lieu = ",".join(f"{cle}={valeur}" for cle, valeur in (("file", fichier), ("line", ligne)) if valeur)
    # Une annotation tient sur une ligne : GitHub demande d'y encoder les sauts.
    message = message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    print(f"::{niveau} {lieu}::{message}" if lieu else f"::{niveau}::{message}")


def ligne(texte, motif):
    """Numéro de la première ligne de texte où figure le motif (regex), ou None."""
    for numero, contenu in enumerate(texte.splitlines(), 1):
        if re.search(motif, contenu):
            return numero
    return None


def verifier_config(hors_ligne):
    chemin = Path("config.yaml")
    if not chemin.is_file():
        signaler("error", "config.yaml est absent de la racine du dépôt.")
        return
    texte = chemin.read_text(encoding="utf-8")

    def erreur(message, ligne_=None):
        signaler("error", message, "config.yaml", ligne_)

    def avertir(message, ligne_=None):
        signaler("warning", message, "config.yaml", ligne_)

    def cle(nom):
        return ligne(texte, rf"^\s*{nom}\s*:")

    try:
        config = yaml.safe_load(texte)
    except yaml.YAMLError as exc:
        # context_mark désigne le début de l'élément fautif (une chaîne non
        # refermée, par exemple) ; problem_mark, l'endroit où l'analyse a cédé.
        marque = getattr(exc, "context_mark", None) or getattr(exc, "problem_mark", None)
        detail = " : ".join(filter(None, (getattr(exc, "context", None), getattr(exc, "problem", None)))) or str(exc)
        erreur(f"config.yaml ne se parse pas ({detail}).", marque.line + 1 if marque else None)
        return

    if isinstance(config, dict):
        verifier_credits(config.get("credits"), texte, erreur, avertir, cle, hors_ligne)

    course = config.get("course") if isinstance(config, dict) else None
    if not isinstance(course, dict):
        erreur("config.yaml doit contenir une section « course ».")
        return

    if "courseName" in course:
        erreur("course.courseName a été renommé en course.name.", cle("courseName"))

    # Le dépôt du cours est celui-ci : la copie envoyée à la partie
    # pédagogique le renseigne d'elle-même, et remplace toute valeur posée ici.
    if "repository" in course:
        avertir("course.repository est ignoré : le dépôt du cours est celui-ci, et la copie envoyée à la partie pédagogique le renseigne d'elle-même.",
                cle("repository"))

    nom = course.get("name")
    if not isinstance(nom, str) or not nom.strip():
        erreur("course.name doit donner l'intitulé du cours.", cle("name") or cle("course"))

    # Titres RNCP
    titres = course.get("RNCP")
    if not isinstance(titres, list) or not titres:
        erreur("course.RNCP doit lister au moins un titre RNCP (ex. RNCP40573).", cle("RNCP") or cle("course"))
        titres = []
    valides = []
    for titre in titres:
        if isinstance(titre, str) and re.fullmatch(r"RNCP\d+", titre):
            valides.append(titre)
        else:
            erreur(f"Titre RNCP mal formé : {titre!r} (attendu : RNCP suivi du numéro de fiche, ex. RNCP40573).",
                   ligne(texte, rf"-\s*{re.escape(str(titre))}\s*(#.*)?$"))

    # Blocs : liste éventuellement vide de codes de bloc, écrits comme sur
    # France Compétences — le titre suivi du bloc, d'un seul tenant :
    # « RNCP40573BC06 ».
    blocs = course.get("RNCPBloc")
    if blocs is None:
        blocs = []
    if not isinstance(blocs, list):
        erreur("course.RNCPBloc doit être une liste, éventuellement vide.", cle("RNCPBloc"))
        blocs = []
    blocs_par_titre = {}
    for bloc in blocs:
        if isinstance(bloc, dict):
            # L'ancienne écriture avec une espace, « RNCP40573: BC06 », est lue
            # comme un mapping YAML.
            titre, code = next(iter(bloc.items()), ("", ""))
            erreur(f"« {titre}: {code} » : un bloc s'écrit d'un seul tenant, {titre}{code}.",
                   ligne(texte, rf"{re.escape(str(titre))}\s*:\s"))
            continue
        trouve = re.fullmatch(r"(RNCP\d+)(BC\d+)", bloc) if isinstance(bloc, str) else None
        if not trouve:
            # L'ancienne écriture « RNCP40573:BC06 » reçoit sa correction exacte.
            ancien = re.fullmatch(r"(RNCP\d+):(BC\d+)", bloc) if isinstance(bloc, str) else None
            conseil = f"écrire {''.join(ancien.groups())}" if ancien else "attendu : le titre suivi du bloc, ex. RNCP40573BC06"
            erreur(f"Bloc mal formé : {bloc!r} ({conseil}).", ligne(texte, re.escape(str(bloc))))
            continue
        titre, code = trouve.groups()
        if titre not in valides:
            erreur(f"Le bloc {bloc} relève du titre {titre}, absent de course.RNCP.", ligne(texte, re.escape(bloc)))
            continue
        blocs_par_titre.setdefault(titre, []).append(code)

    duree = course.get("timing")
    if isinstance(duree, bool) or not isinstance(duree, (int, float)) or duree <= 0:
        erreur("course.timing doit donner la durée du module en jours (nombre positif).", cle("timing") or cle("course"))

    if not hors_ligne:
        for titre in valides:
            verifier_fiche(titre, blocs_par_titre.get(titre, []), texte, erreur, avertir)


def verifier_credits(credits, texte, erreur, avertir, cle, hors_ligne):
    """Section credits : facultative, mais exploitable par le workflow Documents si présente."""
    if credits is None:
        return
    if not isinstance(credits, dict):
        erreur("credits doit être une section, avec la liste authors.", cle("credits"))
        return

    auteurs = credits.get("authors")
    if auteurs is None:
        return
    if not isinstance(auteurs, list):
        erreur("credits.authors doit lister les signataires du cours (name, github).", cle("authors"))
        return
    for auteur in auteurs:
        if not isinstance(auteur, dict):
            erreur(f"Signataire mal formé : {auteur!r} (attendu : name, puis la liste github).", cle("authors"))
            continue
        nom = auteur.get("name")
        ligne_ = ligne(texte, rf"name\s*:\s*[\"']?{re.escape(str(nom))}") if nom else cle("authors")
        if not isinstance(nom, str) or not nom.strip():
            erreur("Chaque signataire doit donner son nom (name).", ligne_)
            nom = "?"
        # config.yaml est public : une adresse n'a rien à y faire, les commits
        # se rattachent aux signataires par leurs comptes GitHub.
        if "emails" in auteur:
            avertir(f"Signataire {nom} : emails n'est pas lu, et expose ces adresses à qui lit le dépôt. Retirez-les : les commits sont reconnus par les comptes de la liste github.",
                    cle("emails"))
        # Facultatifs : sans eux, le signataire n'est reconnu dans
        # l'historique que si ses commits portent exactement ce nom.
        comptes = auteur.get("github")
        if comptes is None:
            continue
        if not isinstance(comptes, list):
            erreur(f"Signataire {nom} : github doit lister ses comptes GitHub, un par élément.", ligne_)
            continue
        for compte in comptes:
            login = compte.strip().lstrip("@") if isinstance(compte, str) else ""
            ligne_compte = (ligne(texte, rf"-\s*[\"']?@?{re.escape(login)}[\"']?\s*(#.*)?$") if login else None) or ligne_
            if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", login):
                erreur(f"Signataire {nom} : {compte!r} n'est pas un identifiant de compte GitHub.", ligne_compte)
            elif not hors_ligne:
                verifier_compte(login, erreur, avertir, ligne_compte)


def verifier_compte(login, erreur, avertir, ligne_):
    # Un compte mal orthographié ne serait jamais reconnu dans l'historique :
    # le signataire reparaîtrait parmi les contributeurs sans que rien ne le dise.
    entetes = {"User-Agent": "verification-config.yaml", "Accept": "application/vnd.github+json"}
    # Sans jeton, l'API limite les requêtes par adresse IP, que les runners
    # partagent : le workflow fournit le sien.
    if os.environ.get("GITHUB_TOKEN"):
        entetes["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    requete = urllib.request.Request(f"https://api.github.com/users/{login}", headers=entetes)
    try:
        with urllib.request.urlopen(requete, timeout=30):
            pass
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            erreur(f"Le compte GitHub {login} n'existe pas.", ligne_)
        else:
            avertir(f"Compte GitHub {login} non vérifié : GitHub répond {exc.code}.", ligne_)
    except (OSError, http.client.HTTPException) as exc:
        avertir(f"Compte GitHub {login} non vérifié : GitHub injoignable ({exc}).", ligne_)


def verifier_fiche(titre, codes, texte, erreur, avertir):
    url = FICHE_RNCP.format(titre.removeprefix("RNCP"))
    ligne_titre = ligne(texte, rf"-\s*{titre}\s*(#.*)?$")
    requete = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (verification config.yaml)"})
    try:
        with urllib.request.urlopen(requete, timeout=30) as reponse:
            page = reponse.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            erreur(f"La fiche {titre} est introuvable sur France Compétences : {url}", ligne_titre)
        else:
            avertir(f"Fiche {titre} non vérifiée : France Compétences répond {exc.code}.", ligne_titre)
        return
    except (OSError, http.client.HTTPException) as exc:
        # Une panne du site ne doit pas bloquer un push : on le signale seulement.
        # HTTPException couvre une réponse tronquée (IncompleteRead), qui
        # n'hérite pas d'OSError.
        avertir(f"Fiche {titre} non vérifiée : France Compétences injoignable ({exc}).", ligne_titre)
        return

    debut = page.find(DEBUT_COMPETENCES)
    if debut < 0:
        erreur(f"La fiche {titre} est introuvable sur France Compétences, ou sa page a changé de structure : {url}", ligne_titre)
        return
    fin = page.find(FIN_COMPETENCES, debut)
    competences = page[debut:fin] if fin > 0 else page[debut:]
    # Les blocs y figurent sous la forme « RNCP40573BC06 - intitulé ».
    for code in codes:
        if f"{titre}{code}" not in competences:
            erreur(f"Le bloc {code} n'existe pas dans la fiche {titre} : {url}", ligne(texte, rf"{titre}{code}"))


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    analyseur = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    analyseur.add_argument("--hors-ligne", action="store_true", help="ne consulte ni France Compétences ni GitHub")
    arguments = analyseur.parse_args()

    verifier_config(arguments.hors_ligne)

    print(f"{erreurs} erreur(s)." if erreurs else "Vérification réussie.")
    return 1 if erreurs else 0


if __name__ == "__main__":
    sys.exit(main())
