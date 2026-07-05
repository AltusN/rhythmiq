include .env

.PHONY: dev migration test reset

dev:
	docker compose up -d
	@echo "Waiting for Postgres to accept connections..."
	@for i in $$(seq 1 30); do \
		docker compose exec -T db pg_isready -U $(POSTGRES_USER) >/dev/null 2>&1 && break; \
		sleep 1; \
	done
	backend/.venv/bin/alembic -c backend/alembic.ini upgrade head

migration:
	backend/.venv/bin/alembic -c backend/alembic.ini revision --autogenerate -m "$(name)"

test:
	POSTGRESQL_DATABASE_URL=$(POSTGRESQL_TEST_DATABASE_URL) backend/.venv/bin/alembic -c backend/alembic.ini upgrade head
	cd backend && .venv/bin/pytest

reset:
	docker compose down
	sudo rm -rf db_data
	$(MAKE) dev
