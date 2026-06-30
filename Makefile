.PHONY: install models up down logs analyze reset clean all

install: models

models:
	bash scripts/fetch_models.sh

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f --tail 100

analyze:
	docker compose exec recs-worker python -u analyzer.py --once

stats:
	curl -s http://127.0.0.1:8765/stats | python3 -m json.tool

reset:
	docker compose down -v
	rm -rf data/postgres

clean:
	rm -rf data/models/*.pb

all: install up
