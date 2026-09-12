SEED ?= 0

.PHONY: test bench baselines train eval report

test:
	pytest tests/ -q

bench:
	python -m vygo.env --bench

baselines:
	python -m vygo.baselines

train:
	python -m vygo.train_ppo --seed $(SEED)

eval:
	python -m vygo.evaluate

report:
	python -m vygo.report
