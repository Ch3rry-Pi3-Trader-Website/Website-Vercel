APP_ENV ?= dev
PY ?= python

.PHONY: ingest preprocess label bt-ema bt-bb select forward all

ingest:
	APP_ENV=$(APP_ENV) $(PY) -m app.ingest_cli

preprocess:
	APP_ENV=$(APP_ENV) $(PY) -m app.preprocess_cli

label:
	APP_ENV=$(APP_ENV) $(PY) -m app.label_cli

bt-ema:
	APP_ENV=$(APP_ENV) $(PY) -m app.backtest_cli --strategy momentum

bt-bb:
	APP_ENV=$(APP_ENV) $(PY) -m app.backtest_cli --strategy mean_reversion

select:
	APP_ENV=$(APP_ENV) $(PY) -m app.select_strategy_cli

forward:
	APP_ENV=$(APP_ENV) $(PY) -m app.forward_test_cli

all:
	$(MAKE) ingest
	$(MAKE) preprocess
	$(MAKE) bt-ema
	$(MAKE) bt-bb
	$(MAKE) select
	$(MAKE) forward
