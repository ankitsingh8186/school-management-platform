.PHONY: install test lint fmt up down logs smoke backup

install:
	pip install -r requirements-dev.txt

test:
	python -m unittest discover -s tests -v

lint:
	ruff check . && ruff format --check .

fmt:
	ruff check --fix . && ruff format .

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f --tail 50

smoke:
	scripts/smoke_test.sh

backup:
	scripts/backup.sh
