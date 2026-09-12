SEED ?= 0

.PHONY: test bench baselines train eval report

test:
	python run.py test

bench:
	python run.py bench

baselines:
	python run.py baselines

train:
	python run.py train --seed $(SEED)

eval:
	python run.py eval

report:
	python run.py report
