# Raccourcis (macOS / Linux). Sous Windows, voir docs/PAS_A_PAS.md pour les commandes équivalentes.

install:
	pip install -r requirements.txt && pip install -e .

data:
	python -m aia.cli generate

dbt:
	dbt build --project-dir dbt_project --profiles-dir dbt_project

test:
	python -m pytest -q

naive:
	python -m aia.cli naive

eval:
	python -m aia.cli eval --runs 3

all: data dbt test
