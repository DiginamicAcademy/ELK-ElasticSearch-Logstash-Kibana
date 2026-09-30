"""Génère data/access.log : 7 jours de logs d'accès (format Apache combined)
du site de recrutement fictif qui publie les offres du TP.

Usage : python data/generate_access_logs.py [--lignes 20000] [--seed 42]

Le fichier contient deux anomalies à retrouver dans Kibana :
- un incident applicatif (réponses 503 sur l'API) ;
- un scan de vulnérabilités par un robot (rafale de 404).
Les adresses IP sont prises dans les plages réservées à la documentation (RFC 5737).
"""

from __future__ import annotations

import argparse
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

TZ = timezone(timedelta(hours=2))
FIN = datetime(2026, 9, 30, 0, 0, tzinfo=TZ)
DEBUT = FIN - timedelta(days=7)
INCIDENT = (datetime(2026, 9, 28, 14, 0, tzinfo=TZ), datetime(2026, 9, 28, 14, 45, tzinfo=TZ))
SCAN = datetime(2026, 9, 26, 3, 12, tzinfo=TZ)
IP_ROBOT = "203.0.113.66"

PLAGES_IP = ("192.0.2.", "198.51.100.", "203.0.113.")
AGENTS = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.6 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:143.0) Gecko/20100101 Firefox/143.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.6 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Mobile Safari/537.36",
)
AGENT_ROBOT = "Mozilla/5.0 zgrab/0.x"
VILLES = ("Paris", "Lyon", "Toulouse", "Bordeaux", "Nantes", "Montpellier", "Lille")
MOTS = ("python", "java", "devops", "data", "cloud", "cybersecurite", "react")
CHEMINS_SCAN = ("/wp-login.php", "/.env", "/admin", "/phpmyadmin/", "/.git/config", "/server-status")


def ligne(ip: str, date: datetime, methode: str, chemin: str, statut: int,
          taille: int, referer: str, agent: str) -> str:
    horodatage = date.strftime("%d/%b/%Y:%H:%M:%S %z")
    return (f'{ip} - - [{horodatage}] "{methode} {chemin} HTTP/1.1" {statut} {taille} '
            f'"{referer}" "{agent}"')


def requete_normale(rng: random.Random, date: datetime) -> str:
    ip = rng.choice(PLAGES_IP) + str(rng.randint(1, 254))
    agent = rng.choice(AGENTS)
    tirage = rng.random()
    methode, statut, referer = "GET", 200, "-"
    if tirage < 0.15:
        chemin = "/"
    elif tirage < 0.40:
        chemin = f"/recherche?q={rng.choice(MOTS)}&ville={rng.choice(VILLES)}"
    elif tirage < 0.75:
        numero = rng.randint(1, 5000) if rng.random() > 0.03 else rng.randint(9000, 9999)
        chemin = f"/offres/OFF-{numero:05d}"
        statut = 200 if numero <= 5000 else 404
        referer = "https://jobs.example.org/recherche"
    elif tirage < 0.82:
        methode = "POST"
        chemin = f"/offres/OFF-{rng.randint(1, 5000):05d}/postuler"
        statut = 201
    elif tirage < 0.95:
        chemin = f"/api/offres?ville={rng.choice(VILLES)}&page={rng.randint(1, 5)}"
        if INCIDENT[0] <= date < INCIDENT[1] and rng.random() < 0.6:
            statut = 503
        elif rng.random() < 0.002:
            statut = 500
    else:
        chemin = "/static/app.js"
        statut = 304 if rng.random() < 0.5 else 200
    taille = 0 if statut in (201, 304) else rng.randint(300, 48000)
    return ligne(ip, date, methode, chemin, statut, taille, referer, agent)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--lignes", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--sortie", type=Path, default=Path(__file__).with_name("access.log"))
    args = parser.parse_args()

    rng = random.Random(args.seed)
    duree = (FIN - DEBUT).total_seconds()
    evenements: list[tuple[datetime, str]] = []

    for _ in range(args.lignes):
        date = DEBUT + timedelta(seconds=rng.uniform(0, duree))
        evenements.append((date, requete_normale(rng, date)))

    # Pendant l'incident, l'API est aussi davantage sollicitée (réessais des clients).
    for _ in range(400):
        date = INCIDENT[0] + timedelta(seconds=rng.uniform(0, 2700))
        chemin = f"/api/offres?ville={rng.choice(VILLES)}&page=1"
        evenements.append((date, ligne(rng.choice(PLAGES_IP) + str(rng.randint(1, 254)), date,
                                       "GET", chemin, 503, rng.randint(150, 400), "-",
                                       rng.choice(AGENTS))))

    # Scan de vulnérabilités : 300 requêtes en 5 minutes depuis une seule IP.
    for i in range(300):
        date = SCAN + timedelta(seconds=i)
        evenements.append((date, ligne(IP_ROBOT, date, "GET", rng.choice(CHEMINS_SCAN), 404,
                                       rng.randint(150, 400), "-", AGENT_ROBOT)))

    evenements.sort(key=lambda e: e[0])
    args.sortie.write_text("\n".join(texte for _, texte in evenements) + "\n", encoding="utf-8")
    print(f"{len(evenements)} lignes écrites dans {args.sortie}")


if __name__ == "__main__":
    main()
