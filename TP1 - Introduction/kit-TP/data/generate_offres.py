"""Génère un jeu de données fictif d'offres d'emploi IT au format NDJSON.

Usage : python data/generate_offres.py --n 5000 --seed 42 --out data/offres.ndjson
Le résultat est déterministe pour un même seed (reproductible entre apprenants).
"""

from __future__ import annotations

import argparse
import json
import random
from datetime import date, timedelta
from pathlib import Path

VILLES = {  # ville: (lat, lon)
    "Paris": (48.8566, 2.3522), "Lyon": (45.7640, 4.8357), "Marseille": (43.2965, 5.3698),
    "Toulouse": (43.6047, 1.4442), "Montpellier": (43.6108, 3.8767), "Bordeaux": (44.8378, -0.5792),
    "Nantes": (47.2184, -1.5536), "Lille": (50.6292, 3.0573), "Rennes": (48.1173, -1.6778),
    "Strasbourg": (48.5734, 7.7521), "Nice": (43.7102, 7.2620), "Grenoble": (45.1885, 5.7245),
}
POIDS_VILLES = [30, 12, 6, 9, 7, 8, 8, 7, 5, 4, 2, 2]

METIERS = {
    "Développeur Python": ["Python", "Django", "FastAPI", "PostgreSQL", "Docker", "Git"],
    "Développeur Java": ["Java", "Spring Boot", "Maven", "Kafka", "Docker", "Git"],
    "Data Engineer": ["Python", "Spark", "Airflow", "SQL", "Kafka", "Elasticsearch"],
    "Data Scientist": ["Python", "Pandas", "scikit-learn", "PyTorch", "SQL", "MLflow"],
    "Ingénieur DevOps": ["Docker", "Kubernetes", "Terraform", "Ansible", "GitLab CI", "Prometheus"],
    "Administrateur Systèmes": ["Linux", "Ansible", "Bash", "VMware", "Prometheus", "Elasticsearch"],
    "Analyste Cybersécurité": ["SIEM", "Elasticsearch", "Linux", "Python", "ISO 27001", "EBIOS RM"],
    "Développeur Front-end": ["TypeScript", "React", "Vue.js", "CSS", "Vite", "Git"],
    "Architecte Cloud": ["AWS", "Azure", "Kubernetes", "Terraform", "Réseau", "Sécurité"],
    "Administrateur Bases de Données": ["PostgreSQL", "MongoDB", "Elasticsearch", "Redis", "Linux", "SQL"],
}
NIVEAUX = ["Junior", "Confirmé", "Senior", "Lead"]
ENTREPRISES = [
    "Aurore Numérique", "Cévennes Data", "Garrigue Cloud", "Littoral Systèmes", "Mistral Logiciels",
    "Nexa Conseil", "Occitane Tech", "Pic Saint-Loup Labs", "Quartz Informatique", "Rivage Analytics",
    "Sud Réseaux", "Tramontane Digital", "Vallée Data", "Zénith Services",
]
CONTRATS = ["CDI", "CDD", "Alternance", "Freelance", "Stage"]
POIDS_CONTRATS = [55, 12, 15, 13, 5]
TELETRAVAIL = ["aucun", "partiel", "total"]
PHRASES = [
    "Vous rejoignez une équipe de {taille} personnes travaillant sur des projets {domaine}.",
    "Vous participez à la conception et au développement de nouvelles fonctionnalités.",
    "Vous contribuez à l'amélioration continue de la qualité et des performances.",
    "Vous travaillez en méthode agile avec des sprints de deux semaines.",
    "Vous accompagnez les équipes dans la mise en production et le suivi opérationnel.",
    "Une bonne maîtrise de {c1} et de {c2} est indispensable.",
    "Une première expérience avec {c3} serait appréciée.",
    "Vous rédigez la documentation technique et partagez vos connaissances.",
    "Le poste implique des échanges réguliers avec les clients et les chefs de projet.",
]
DOMAINES = ["bancaires", "de santé", "industriels", "e-commerce", "publics", "énergétiques", "logistiques"]
SALAIRE_BASE = {"Junior": 36000, "Confirmé": 45000, "Senior": 55000, "Lead": 65000}
EXPERIENCE = {"Junior": (0, 2), "Confirmé": (2, 5), "Senior": (5, 10), "Lead": (8, 15)}


def generer_offre(i: int, rng: random.Random, aujourd_hui: date) -> dict:
    metier, stack = rng.choice(list(METIERS.items()))
    niveau = rng.choice(NIVEAUX)
    contrat = rng.choices(CONTRATS, POIDS_CONTRATS)[0]
    ville = rng.choices(list(VILLES), POIDS_VILLES)[0]
    lat, lon = VILLES[ville]
    competences = rng.sample(stack, k=rng.randint(3, 5))
    c1, c2, c3 = rng.sample(stack, k=3)

    phrases = rng.sample(PHRASES, k=5)
    description = " ".join(
        p.format(taille=rng.randint(4, 30), domaine=rng.choice(DOMAINES), c1=c1, c2=c2, c3=c3)
        for p in phrases
    )

    offre: dict = {
        "id": f"OFF-{i:05d}",
        "titre": f"{metier} {niveau}" if contrat not in ("Alternance", "Stage") else f"{metier} ({contrat})",
        "entreprise": rng.choice(ENTREPRISES),
        "description": description,
        "competences": competences,
        "ville": ville,
        # léger bruit pour éviter que toutes les offres d'une ville soient au même point
        "localisation": {"lat": round(lat + rng.uniform(-0.05, 0.05), 5),
                         "lon": round(lon + rng.uniform(-0.05, 0.05), 5)},
        "contrat": contrat,
        "teletravail": rng.choices(TELETRAVAIL, [25, 60, 15])[0],
        "experience_annees": rng.randint(*EXPERIENCE[niveau]),
        "date_publication": (aujourd_hui - timedelta(days=rng.randint(0, 180))).isoformat(),
    }
    if contrat not in ("Alternance", "Stage", "Freelance"):
        base = SALAIRE_BASE[niveau] + (6000 if ville == "Paris" else 0)
        salaire_min = base + rng.randint(-3, 5) * 1000
        offre["salaire_min"] = salaire_min
        offre["salaire_max"] = salaire_min + rng.randint(3, 10) * 1000
    return offre


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=5000, help="nombre d'offres")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--date-ref", default="2026-09-30", help="date de référence (AAAA-MM-JJ)")
    parser.add_argument("--out", type=Path, default=Path(__file__).with_name("offres.ndjson"))
    args = parser.parse_args()

    rng = random.Random(args.seed)
    ref = date.fromisoformat(args.date_ref)
    with args.out.open("w", encoding="utf-8") as f:
        for i in range(1, args.n + 1):
            f.write(json.dumps(generer_offre(i, rng, ref), ensure_ascii=False) + "\n")
    print(f"{args.n} offres écrites dans {args.out}")


if __name__ == "__main__":
    main()
