.PHONY: run install test clean

run:
	flask run

install:
	pip install -r requirements.txt

test:
	python -m pytest

clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete

db-init:
	flask db init

db-migrate:
	flask db migrate

db-upgrade:
	flask db upgrade

prod:
	gunicorn -w 4 "app:create_app()"