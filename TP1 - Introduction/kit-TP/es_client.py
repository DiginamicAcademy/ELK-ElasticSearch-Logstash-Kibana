"""Connexion partagée au cluster (lit ES_URL et ELASTIC_PASSWORD depuis .env)."""

from __future__ import annotations

import os

from dotenv import find_dotenv, load_dotenv
from elasticsearch import Elasticsearch

INDEX = "offres"


def get_client() -> Elasticsearch:
    load_dotenv(find_dotenv(usecwd=True))  # .env du dossier courant ou de ses parents
    password = os.environ.get("ELASTIC_PASSWORD")
    if not password:
        raise SystemExit("ELASTIC_PASSWORD absent : lancez le script depuis le dossier du TP (fichier .env).")
    return Elasticsearch(
        os.environ.get("ES_URL", "http://localhost:9200"),
        basic_auth=("elastic", password),
        request_timeout=30,
    )
