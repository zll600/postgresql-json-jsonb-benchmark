# PostgreSQL JSON vs JSONB Benchmark Makefile
# Supports both Docker Compose V1 and V2

# Detect Docker Compose command
DOCKER_COMPOSE := $(shell if docker compose version >/dev/null 2>&1; then echo "docker compose"; else echo "docker-compose"; fi)

.PHONY: help build run quick clean logs shell db-only results setup mysql-run mysql-quick mysql-db-only mysql-shell mysql-clean

# Default target
help: ## Show this help message
	@echo "PostgreSQL JSON vs JSONB Benchmark"
	@echo "=================================="
	@echo "Using: $(DOCKER_COMPOSE)"
	@echo ""
	@echo "Available targets:"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

setup: ## Create .env file from template if it doesn't exist
	@if [ ! -f .env ]; then \
	cp .env.example .env; \
	echo "✅ Created .env file from template"; \
	echo "📝 Edit .env file to customize settings"; \
	else \
	echo "ℹ️  .env file already exists"; \
	fi
	@mkdir -p results

build: setup ## Build Docker containers
	@echo "Building containers..."
	@$(DOCKER_COMPOSE) -f docker-compose-pgsql.yml -f docker-compose-pgsql-py.yml build

run: build ## Run full benchmark (1M records)
	@echo "Starting full benchmark..."
	@$(DOCKER_COMPOSE) -f docker-compose-pgsql.yml -f docker-compose-pgsql-py.yml up --abort-on-container-exit --exit-code-from benchmark_runner

quick: build ## Run quick test (10K records)
	@echo "Starting quick test..."
	@BENCHMARK_RECORDS=10000 $(DOCKER_COMPOSE) -f docker-compose-pgsql.yml -f docker-compose-pgsql-py.yml up --abort-on-container-exit --exit-code-from benchmark_runner

db-only: setup ## Start only PostgreSQL database
	@echo "Starting PostgreSQL only..."
	@$(DOCKER_COMPOSE) -f docker-compose-pgsql.yml up postgres

clean: ## Clean up containers, volumes, and images
	@echo "Cleaning up..."
	@$(DOCKER_COMPOSE) -f docker-compose-pgsql.yml -f docker-compose-pgsql-py.yml down -v --remove-orphans
	@docker volume rm postgresql-json-jsonb-benchmark_postgres_data 2>/dev/null || true
	@docker system prune -f
	@echo "Cleanup completed"

logs: ## Show logs from all services
	@$(DOCKER_COMPOSE) -f docker-compose-pgsql.yml -f docker-compose-pgsql-py.yml logs -f

shell: ## Access database shell
	@echo "Connecting to database..."
	@$(DOCKER_COMPOSE) -f docker-compose-pgsql.yml exec postgres psql -U ${PG_USER:-benchmark_user} -d ${PG_DATABASE:-json_benchmark_db}

shell-local: ## Access database from host (localhost:5433)
	@echo "Connecting to database from host..."
	@psql -h localhost -p 5433 -U ${PG_USER:-benchmark_user} -d ${PG_DATABASE:-json_benchmark_db}

results: ## Copy results from container (if running)
	@echo "📊 Copying results..."
	@if [ -f "./results/benchmark_results.json" ]; then \
	echo "📁 Results found in ./results/benchmark_results.json"; \
	echo "📈 Summary:"; \
	python3 -c "import json; data=json.load(open('./results/benchmark_results.json')); insert=data.get('insert_performance',{}); print(f'INSERT: JSON {insert.get(\"json_time_seconds\",0)}s vs JSONB {insert.get(\"jsonb_time_seconds\",0)}s')" 2>/dev/null || echo "Use 'cat ./results/benchmark_results.json' to view results"; \
	else \
	echo "❌ No results found. Run 'make run' first."; \
	fi

# Advanced targets
rebuild: clean build ## Clean rebuild everything

test-env: ## Test environment setup
	@echo "🧪 Testing environment..."
	@docker version
	@echo "Docker Compose: $(DOCKER_COMPOSE)"
	@$(DOCKER_COMPOSE) version
	@if [ -f .env ]; then echo "✅ .env file exists"; else echo "❌ .env file missing - run 'make setup'"; fi

# Development targets
dev-db: ## Start database in development mode with exposed port
	@echo "Starting development database..."
	@$(DOCKER_COMPOSE) -f docker-compose-pgsql.yml up postgres -d
	@echo "Database available on localhost:5433"
	@echo "Connection: postgresql://benchmark_user:benchmark_pass_2024@localhost:5433/json_benchmark_db"

stop: ## Stop all services
	@$(DOCKER_COMPOSE) -f docker-compose-pgsql.yml -f docker-compose-pgsql-py.yml stop

restart: stop run ## Restart benchmark

# CI/CD targets
ci-test: ## Run benchmark for CI/CD (quick test)
	@echo "Running CI test..."
	@BENCHMARK_RECORDS=1000 $(DOCKER_COMPOSE) -f docker-compose-pgsql.yml -f docker-compose-pgsql-py.yml up --abort-on-container-exit --exit-code-from benchmark_runner
	@$(DOCKER_COMPOSE) -f docker-compose-pgsql.yml -f docker-compose-pgsql-py.yml down -v

# Custom record count
run-custom: ## Run with custom record count (use RECORDS=number)
	@echo "Running with $(RECORDS) records..."
	@BENCHMARK_RECORDS=$(RECORDS) $(DOCKER_COMPOSE) -f docker-compose-pgsql.yml -f docker-compose-pgsql-py.yml up --abort-on-container-exit --exit-code-from benchmark_runner

# ================================
# MySQL Benchmark Targets
# ================================

mysql-build: setup ## Build MySQL Docker containers
	@echo "Building MySQL containers..."
	@$(DOCKER_COMPOSE) -f docker-compose-mysql.yml -f docker-compose-mysql-py.yml build

mysql-run: mysql-build ## Run MySQL benchmark (1M records)
	@echo "Starting MySQL benchmark..."
	@$(DOCKER_COMPOSE) -f docker-compose-mysql.yml -f docker-compose-mysql-py.yml up --abort-on-container-exit --exit-code-from mysql_benchmark_runner

mysql-quick: mysql-build ## Run quick MySQL test (10K records)
	@echo "Starting quick MySQL test..."
	@BENCHMARK_RECORDS=10000 $(DOCKER_COMPOSE) -f docker-compose-mysql.yml -f docker-compose-mysql-py.yml up --abort-on-container-exit --exit-code-from mysql_benchmark_runner

mysql-db-only: setup ## Start only MySQL database
	@echo "Starting MySQL only..."
	@$(DOCKER_COMPOSE) -f docker-compose-mysql.yml up mysql

mysql-shell: ## Access MySQL database shell
	@echo "Connecting to MySQL..."
	@$(DOCKER_COMPOSE) -f docker-compose-mysql.yml exec mysql mysql -u ${MYSQL_USER:-benchmark_user} -p${MYSQL_PASSWORD:-benchmark_pass_2024} ${MYSQL_DATABASE:-json_benchmark_db}

mysql-shell-local: ## Access MySQL from host (localhost:3307)
	@echo "Connecting to MySQL from host..."
	@mysql -h localhost -P 3307 -u ${MYSQL_USER:-benchmark_user} -p${MYSQL_PASSWORD:-benchmark_pass_2024} ${MYSQL_DATABASE:-json_benchmark_db}

mysql-clean: ## Clean up MySQL containers and volumes
	@echo "Cleaning up MySQL..."
	@$(DOCKER_COMPOSE) -f docker-compose-mysql.yml -f docker-compose-mysql-py.yml down -v --remove-orphans
	@docker volume rm postgresql-json-jsonb-benchmark_mysql_data 2>/dev/null || true
	@echo "MySQL cleanup completed"

mysql-results: ## Show MySQL benchmark results
	@echo "MySQL Results..."
	@if [ -f "./results/mysql_benchmark_results.json" ]; then \
		echo "Results found in ./results/mysql_benchmark_results.json"; \
		echo "Summary:"; \
		python3 -c "import json; data=json.load(open('./results/mysql_benchmark_results.json')); insert=data.get('insert_performance',{}); print(f'INSERT: JSON {insert.get(\"json_time_seconds\",0)}s')" 2>/dev/null || echo "Use 'cat ./results/mysql_benchmark_results.json' to view results"; \
	else \
		echo "No results found. Run 'make mysql-run' first."; \
	fi

mysql-run-custom: ## Run MySQL with custom record count (use RECORDS=number)
	@echo "Running MySQL with $(RECORDS) records..."
	@BENCHMARK_RECORDS=$(RECORDS) $(DOCKER_COMPOSE) -f docker-compose-mysql.yml -f docker-compose-mysql-py.yml up --abort-on-container-exit --exit-code-from mysql_benchmark_runner

# ================================
# Combined Benchmark Targets
# ================================

run-all: ## Run both PostgreSQL and MySQL benchmarks
	@echo "Running all benchmarks..."
	@$(MAKE) run
	@$(MAKE) mysql-run

quick-all: ## Run quick tests for both databases
	@echo "Running all quick tests..."
	@$(MAKE) quick
	@$(MAKE) mysql-quick

clean-all: clean mysql-clean ## Clean up all containers and volumes
	@echo "All cleanup completed"

results-all: results mysql-results ## Show all benchmark results
	@echo "All results displayed"

compare: ## Compare PostgreSQL and MySQL benchmark results
	@echo "Comparing benchmark results..."
	@python3 compare_results.py
