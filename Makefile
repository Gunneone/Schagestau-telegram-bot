# Makefile for Schagestau Telegram Bot

.PHONY: help install init test run docker-build docker-up docker-down docker-logs docker-restart clean

help:
	@echo "Available commands:"
	@echo "  make install         - Install dependencies"
	@echo "  make init           - Initialize storage files"
	@echo "  make test           - Run in dry-run mode"
	@echo "  make run            - Run the bot"
	@echo "  make docker-build   - Build Docker image"
	@echo "  make docker-up      - Start with Docker Compose"
	@echo "  make docker-down    - Stop Docker Compose"
	@echo "  make docker-logs    - View Docker logs"
	@echo "  make docker-restart - Restart Docker containers"
	@echo "  make clean          - Clean up temporary files"

install:
	pip install -r requirements.txt

init:
	python scripts/init_db.py

test:
	python main.py --run-once --dry-run

run:
	python main.py

docker-build:
	docker-compose build

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

docker-restart:
	docker-compose restart

clean:
	rm -f last_fetch.json bot.log
	rm -rf __pycache__ src/__pycache__ scripts/__pycache__
	rm -rf data/
	find . -name "*.pyc" -delete
	find . -name "*.pyo" -delete
