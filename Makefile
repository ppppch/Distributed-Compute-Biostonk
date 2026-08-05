PYTHON ?= python3
COORDINATOR_HOST ?= 0.0.0.0
COORDINATOR_PORT ?= 8000
COORDINATOR_URL ?= http://127.0.0.1:$(COORDINATOR_PORT)
WORKER_ID ?= worker-a

.PHONY: install test coordinator worker submit-demo demo-status workers baseline prepare train baseline_run split worker_local legacy-baseline legacy-workers clean

install:
	$(PYTHON) -m pip install -r requirements.txt

test:
	$(PYTHON) -m pytest -q

coordinator:
	COORDINATOR_HOST=$(COORDINATOR_HOST) COORDINATOR_PORT=$(COORDINATOR_PORT) \
	$(PYTHON) -m uvicorn server.server:app --host $(COORDINATOR_HOST) --port $(COORDINATOR_PORT)

worker:
	COORDINATOR_URL=$(COORDINATOR_URL) WORKER_ID=$(WORKER_ID) \
	$(PYTHON) -m client.worker

submit-demo:
	COORDINATOR_URL=$(COORDINATOR_URL) $(PYTHON) -m client.demo_client submit

demo-status:
	COORDINATOR_URL=$(COORDINATOR_URL) JOB_ID=$(JOB_ID) \
	$(PYTHON) -m client.demo_client status $(if $(JOB_ID),$(JOB_ID),)

workers:
	COORDINATOR_URL=$(COORDINATOR_URL) $(PYTHON) -m client.demo_client workers

# --- Baseline phase (baseline/) ---

prepare:
	cd baseline && ../$(PYTHON) prepare_dataset.py

train:
	cd baseline && ../$(PYTHON) train_model.py

baseline_run:
	cd baseline && ../$(PYTHON) run_baseline.py

# Runs all three baseline steps, in order
baseline: prepare train baseline_run
	@echo "Baseline pipeline complete. Model saved to shared/baseline_model.joblib"

# --- Client-side distributed phase (client/) ---

split:
	cd client && ../$(PYTHON) split_job.py

worker_local:
	cd client && ../$(PYTHON) run_worker_local.py

# --- Legacy local simulation and tests ---

legacy-baseline:
	$(PYTHON) prepare_dataset.py && $(PYTHON) train_model.py && $(PYTHON) run_baseline.py

legacy-workers:
	$(PYTHON) split_job.py
	$(PYTHON) run_worker.py job_part1.npz results_part1.npz --label "Part 1"
	$(PYTHON) run_worker.py job_part2.npz results_part2.npz --label "Part 2"
	$(PYTHON) combine_and_verify.py

# --- Removes all generated files across every folder ---

clean:
	rm -f baseline/train.npz baseline/job.npz baseline/baseline_predictions.npz baseline/baseline_report.json
	rm -f shared/baseline_model.joblib
	rm -f client/job_part1.npz client/job_part2.npz client/results_part1.npz client/results_part2.npz
	rm -f train.npz job.npz baseline_model.joblib baseline_predictions.npz baseline_report.json job_part1.npz job_part2.npz results_part1.npz results_part2.npz
	@echo "Cleaned up generated files."