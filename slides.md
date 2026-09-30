---
marp: true
theme: default
style: |
  section {background-color: #121114}
  h1,h2,h3 {color: #8393f0}
  p,ul,li,td,th {color: #ccc}
  section table td {background-color: #121114}
  section table th {background-color: #272133; font-weight: bolder}
  pre {background-color: #17151a; color: #ccc}
  blockquote {border: 2px green solid; border-left-width: 15px; padding: 0.5em 15px;font-style: italic }
paginate: true
header: "ELK : Elasticsearch, Logstash, Kibana"
footer: "![height:20px](https://raw.githubusercontent.com/DiginamicInternal/PublicAssets/refs/heads/main/Logo-diginamic-color-blk.png)"
---

<!-- _paginate: false -->

# La stack ELK

Du TP d'introduction à Logstash

EISI Data

---

## Aujourd'hui

1. **Remettre à plat** ce que vous avez fait dans le TP
2. **Regarder sous le capot** : cluster, écriture, recherche
3. **Changer de problème** : des offres aux logs
4. **Découvrir Logstash**
5. **Préparer** le TP Logstash

Référence écrite : le **support de cours**.

---

## La stack en une image

```text
 Sources ──▶ Logstash ──▶ Elasticsearch ◀── Kibana ◀── Navigateur
            collecter     stocker            explorer
            transformer   chercher           visualiser
```

- **E** : stocke et cherche
- **L** : collecte et transforme
- **K** : explore et montre

---

## Qu'avez-vous construit ?

- Un cluster **Elasticsearch** + **Kibana** en Docker
- Un index `offres` : 5 000 offres, mapping explicite
- `ingest.py` : chargement en masse
- `search.py` : un moteur de recherche

> Et le « L » ? Il manquait : votre script Python en tenait lieu.

---

<!-- _paginate: false -->

# 1. Remettre à plat

Les notions du TP

---

## Document, index, mapping

| Elasticsearch | MongoDB | SQL |
| --- | --- | --- |
| Document | Document | Ligne |
| Index | Collection | Table |
| Mapping | Validator | `CREATE TABLE` |

> Le mapping décide de **ce qu'on pourra faire** avec chaque champ.

---

## `text` ou `keyword` ?

| | `text` | `keyword` |
| --- | --- | --- |
| Stockage | Mots analysés | Valeur exacte |
| Pour | Chercher | Filtrer, trier, compter |
| Exemple | `description` | `ville` |

Et pour `titre` ? **Les deux** : `titre` + `titre.brut`

---

## Le piège du mapping dynamique

```text
PUT essai2/_doc/1
{ "salaire": "45000" }
```

- `salaire` devient du **texte**
- Trier donne « 100000 » avant « 45000 »
- Le type ne changera plus

> Réponse du TP : mapping explicite + `"dynamic": "strict"`

---

## L'analyseur

Texte : « Les développeuses travaillaient sur l'analyse des données »

| Analyseur | Ce qu'il garde |
| --- | --- |
| `standard` | Tous les mots, en minuscules ; « l'analyse » reste entier |
| `french` | Des racines ; ni « les », ni « sur », ni « l' » |

Appliqué **deux fois** : à l'indexation **et** à la question.

---

## Question : pourquoi 0 résultat ?

```text
GET offres/_search
{ "query": { "term": { "ville": "paris" } } }
```

<!-- Réponse : term n'analyse pas la valeur ; ville est un keyword qui contient "Paris". -->

---

## `match` ou `term`

| | `match` | `term` |
| --- | --- | --- |
| Analyse la question | Oui | **Non** |
| Champ visé | `text` | `keyword`, nombre, date |
| Exemple | « projets bancaires » | `"Paris"` |

> `term` + `text` = presque toujours une erreur.

---

## La requête `bool`

| Clause | Obligatoire | Score |
| --- | --- | --- |
| `must` | Oui | Oui |
| `filter` | Oui | Non |
| `should` | Bonus | Oui |
| `must_not` | Exclusion | Non |

Critère exact → `filter` : pas de score, **mis en cache**.

---

## Le score (BM25)

Un document monte quand le mot est :

1. **fréquent** dans le document
2. **rare** dans l'index
3. dans un **champ court**

`titre^3` : le titre compte trois fois plus.

---

## Agréger

| Regroupement | Métrique |
| --- | --- |
| `terms`, `range`, `date_histogram` | `avg`, `min`, `max`, `stats` |
| `GROUP BY` | `AVG()`, `COUNT()` |

Imbriquées : salaire moyen **par** ville.

> Question : pourquoi `terms` sur `titre` échoue-t-il ?

---

## Ingérer : `_bulk` + `_id` métier

- **`_bulk`** : des milliers d'écritures en une requête
- Un statut **par document** : une erreur n'arrête pas le lot
- **`_id` = `id` de l'offre** : relancer ne crée pas de doublon

> C'est l'**idempotence**.

---

## Quasi temps réel

- Écrit → lisible par son `_id` : **tout de suite**
- Écrit → trouvé par une recherche : **après le refresh** (1 s)

D'où le `_refresh` à la fin d'`ingest.py`.

---

<!-- _paginate: false -->

# 2. Sous le capot

Ce que le TP ne montrait pas

---

## Nœuds, shards, répliques

```text
   nœud-1              nœud-2
 ┌──────────┐        ┌──────────┐
 │ P0   R1  │        │ P1   R0  │
 └──────────┘        └──────────┘
 P = primaire     R = réplique (jamais avec son primaire)
```

- Primaires : **fixés** à la création
- Répliques : **modifiables** à chaud

---

## Question : pourquoi jaune ?

```text
PUT offres/_settings
{ "index": { "number_of_replicas": 1 } }

GET _cluster/health
```

<!-- Réponse : un seul nœud, la réplique ne peut pas être placée avec son primaire. -->

---

## Vert, jaune, rouge

| Couleur | Signifie |
| --- | --- |
| Vert | Tout est alloué |
| Jaune | Des répliques manquent |
| Rouge | Un primaire manque : données indisponibles |

Premier réflexe : `GET _cluster/allocation/explain`

---

## Le trajet d'une écriture

1. Un nœud reçoit le document
2. Il choisit le shard : `hash(_id) % nb_primaires`
3. Le **primaire** écrit, les **répliques** copient
4. **Refresh** : le document devient cherchable

> Voilà pourquoi le nombre de primaires est figé.

---

## Le trajet d'une recherche

1. **Query** : chaque shard renvoie ses meilleurs `_id`
2. **Fetch** : on récupère seulement les documents affichés

> Page 1 000 = beaucoup de travail → limite de 10 000 résultats

---

## Trois langages

| Langage | Où | Pour |
| --- | --- | --- |
| Query DSL | API, Python | Recherche applicative |
| ES\|QL | Discover, API | Analyser |
| KQL | Barre Kibana | Filtrer vite |

---

## ES|QL : l'exercice 4.1 en 4 lignes

```text
FROM offres
| WHERE salaire_min IS NOT NULL
| STATS salaire_moyen = AVG(salaire_min) BY ville
| SORT salaire_moyen DESC
```

À essayer dans **Discover**, mode ES|QL.

---

<!-- _paginate: false -->

# 3. Changer de problème

Des offres aux logs

---

## Une offre, une ligne de log

| | Offre | Log |
| --- | --- | --- |
| Nature | Entité | Événement |
| Format | JSON propre | Ligne de texte |
| Arrivée | Une fois | En continu |
| Modifiée ? | Oui | Jamais |
| Temps | Un champ | **L'axe principal** |

---

## Une ligne de log d'accès

```text
192.0.2.10 - - [28/Sep/2026:14:03:11 +0200]
    "GET /api/offres HTTP/1.1" 503 212 "-" "Mozilla/5.0"
```

(une seule ligne dans le fichier, coupée ici pour la lecture)

> Comment compter les erreurs 503 par heure ?

---

## Ce qui manque

Pour répondre, il faut :

- **découper** la ligne en champs : IP, URL, code, taille
- **typer** : `503` est un nombre
- **dater** : l'heure de l'événement, pas celle de lecture
- **suivre** un fichier qui grossit, reprendre après un arrêt

> `ingest.py` ne sait rien faire de tout cela.

---

<!-- _paginate: false -->

# 4. Logstash

Collecter et transformer

---

## Le rôle de Logstash

Un **ETL de flux** :

- **Extraire** : fichiers, Kafka, bases SQL, HTTP, agents
- **Transformer** : découper, typer, dater, enrichir
- **Charger** : Elasticsearch… et ailleurs

---

## Un pipeline

```text
 input ──▶ filter ──▶ output
 lire      transformer  envoyer
```

```text
input  { stdin { } }
filter { mutate { add_field => { "source" => "cours" } } }
output { stdout { codec => rubydebug } }
```

---

## `grok` : découper une ligne

```text
grok { match => { "message" => "%{COMBINEDAPACHELOG}" } }
```

| Champ | Valeur |
| --- | --- |
| `source.address` | `192.0.2.10` |
| `http.response.status_code` | `503` |

Tester : Kibana → Dev Tools → **Grok Debugger**

---

## `date` : la bonne heure

```text
date { match => ["timestamp", "dd/MMM/yyyy:HH:mm:ss Z"] }
```

- Sans lui : `@timestamp` = heure de **lecture**
- Avec lui : `@timestamp` = heure de l'**événement**

> Graphique faux = souvent un `@timestamp` faux.

---

## ECS : parler la même langue

| Au lieu de… | ECS |
| --- | --- |
| `clientip`, `remote_addr` | `source.address` |
| `status`, `code` | `http.response.status_code` |
| `agent`, `ua` | `user_agent.original` |

Un tableau de bord, **toutes** les sources.

---

## Index ou data stream ?

| | Index | Data stream |
| --- | --- | --- |
| Pour | Offres | Logs |
| Écriture | Modifiable | Ajout seul |
| `@timestamp` | Facultatif | Obligatoire |
| Taille | Un index | Nouvel index par tranche |

Nom d'un data stream : `logs-web-default`

---

## Ne rien perdre

- **File persistée** : survit à un redémarrage
- **Dead letter queue** : garde les documents refusés
- **« Au moins une fois »** : doublons possibles…

> … neutralisés par un `_id` métier. Comme dans `ingest.py`.

---

## Logstash ou autre chose ?

| Outil | Quand |
| --- | --- |
| Logstash | Plusieurs sources, logique riche |
| Ingest pipeline | Transformations simples, dans Elasticsearch |
| Elastic Agent, Beats | Collecter sur la machine source |

---

<!-- _paginate: false -->

# 5. Vers le TP Logstash

---

## Dans le prochain TP

1. Ajouter **Logstash** à votre stack Docker
2. Recharger `offres` avec Logstash au lieu d'`ingest.py`
3. Parser des **logs d'accès** du site d'offres
4. Les envoyer dans un **data stream**
5. **Enquêter** dans Kibana : un incident, un robot suspect
6. Construire un **tableau de bord**

---

## Questions à garder en tête

- Pourquoi l'index `offres` rejettera-t-il les champs ajoutés par Logstash ?
- Que devient une ligne que `grok` ne sait pas lire ?
- Comment rejouer une ingestion sans doublon ?
- Qui a le droit d'écrire dans Elasticsearch ?

---

## À retenir

1. Le **mapping** décide de ce qui est possible
2. L'analyseur agit **à l'écriture et à la lecture**
3. Critère exact → **`filter`**
4. `_id` métier → **idempotence**
5. Logstash = **input → filter → output**
6. Entité → **index** ; événement → **data stream**

---

## Pour aller plus loin

Dans le **support de cours** :

- cycle de vie des données et sauvegardes
- dimensionnement des shards
- sécurité et supervision de la stack
- alternatives : OpenSearch, Loki, ClickHouse

Documentation : **elastic.co/docs**
