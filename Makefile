.PHONY: init status continue deploy split refresh-catalog

PYTHON ?= .venv/bin/python
BOOK ?= le-petit-prince

init:
	$(PYTHON) scripts/book.py init $(BOOK) $(ARGS)

status:
	$(PYTHON) scripts/book.py status $(BOOK)

split:
	$(PYTHON) scripts/book.py split $(BOOK)

continue:
	$(PYTHON) scripts/book.py continue $(BOOK)

deploy:
	$(PYTHON) scripts/book.py deploy

refresh-catalog:
	$(PYTHON) scripts/book.py refresh-catalog
