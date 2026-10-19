PY := .venv/bin/python
SESSION ?= tests/fixtures/session.json
WHEN ?= today

# Last week + this week (what was programmed) and the current month (what was logged).
DATE = python3 -c "import datetime as d,calendar as c;t=d.date.today();print($(1))"
MONDAY    := $(shell $(call DATE,t-d.timedelta(days=t.weekday()+7)))
SUNDAY    := $(shell $(call DATE,t+d.timedelta(days=6-t.weekday())))
MONTH_1ST := $(shell $(call DATE,t.replace(day=1)))
MONTH_END := $(shell $(call DATE,t.replace(day=c.monthrange(t.year,t.month)[1])))

.PHONY: help setup data test login push dry history web clean

help:
	@echo "make setup     virtualenv + dependencies + Chromium"
	@echo "make data      create data/ (your personal files, kept out of git) from athlete.example.json"
	@echo "make test      run all tests"
	@echo "make login     log in to Garmin Connect by hand (once)"
	@echo "make push      upload SESSION=$(SESSION) to Garmin, scheduled for WHEN=$(WHEN)"
	@echo "make dry       print the Garmin JSON without uploading"
	@echo "make history   rebuild data/ from data/raw and write data/barra.html with your maxes"
	@echo "make web       download this week and month from WodUp and write data/web.json"

setup:
	python3 -m venv .venv
	$(PY) -m pip install -q --upgrade pip -r requirements.txt
	$(PY) -m playwright install chromium

# data/ is personal and never committed. An existing one is left alone.
data:
	@test -e data/athlete.json || { mkdir -p data/raw data/sessions && cp athlete.example.json data/athlete.json && echo "Created data/athlete.json: put your PRs there."; }

test:
	@PY=$(PY) bash tests/run.sh

login:
	$(PY) garmin.py --login

push:
	$(PY) garmin.py $(SESSION) --schedule $(WHEN)

dry:
	$(PY) garmin.py $(SESSION) --dry-run

history:
	python3 wodup/normalize.py
	python3 wodup/rms.py

# Needs your WodUp session in the browse daemon; gq.sh recovers it from Chrome
# when it has expired. Publishing the page is a separate step: data/web.json is
# served next to web/index.html as data.json.
web:
	wodup/gq.sh Week wodup/queries/week.graphql '{"start":"$(MONDAY)","end":"$(SUNDAY)"}' data/week.json
	wodup/gq.sh Month wodup/queries/month.graphql '{"start":"$(MONTH_1ST)","end":"$(MONTH_END)"}' data/raw/$(shell date +%Y-%m).json
	$(MAKE) -s history
	node tests/extract-logic.mjs > /dev/null
	node web/build.mjs

clean:
	rm -f tests/logic.mjs
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
