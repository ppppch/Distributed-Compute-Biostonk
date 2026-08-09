# Run the single-computer baseline with: make baseline
# Run an individual step with: make X , ex: make prepare

# --- Baseline phase (baseline/) ---

prepare:
	cd baseline && python3 prepare_dataset.py

train:
	cd baseline && python3 train_model.py

baseline_run:
	cd baseline && python3 run_baseline.py

# Runs all three baseline steps, in order
baseline: prepare train baseline_run
	@echo "Baseline pipeline complete. Model saved to shared/baseline_model.joblib"

# --- Client-side distributed phase (client/) ---

split:
	cd client && python3 split_job.py

worker_local:
	cd client && python3 run_worker_local.py

# --- Legacy local simulation and tests ---

legacy-baseline:
	python3 prepare_dataset.py && python3 train_model.py && python3 run_baseline.py

legacy-workers:
	python3 split_job.py
	python3 run_worker.py job_part1.npz results_part1.npz --label "Part 1"
	python3 run_worker.py job_part2.npz results_part2.npz --label "Part 2"
	python3 combine_and_verify.py

test:
	python3 -m unittest discover -s tests -v

# --- Verified clinical compute (run each target in its own terminal) ---

clinical-server:
	BIOSTONK_APPROVED_WORKERS=local-worker-a,local-worker-b python3 -m uvicorn clinical.api:app --host 127.0.0.1 --port 8001

clinical-worker-a:
	WORKER_ID=local-worker-a COORDINATOR_URL=http://127.0.0.1:8001 python3 -m client.clinical_worker

clinical-worker-b:
	WORKER_ID=local-worker-b COORDINATOR_URL=http://127.0.0.1:8001 python3 -m client.clinical_worker

clinical-lan-server:
	BIOSTONK_APPROVED_WORKERS=laptop-a,laptop-b BIOSTONK_REQUIRE_DISTINCT_HOSTS=true python3 -m uvicorn clinical.api:app --host 0.0.0.0 --port 8001

clinical-lan-worker-a:
	WORKER_ID=laptop-a COORDINATOR_URL=$${COORDINATOR_URL:-http://127.0.0.1:8001} python3 -m client.clinical_worker

clinical-lan-worker-b:
	WORKER_ID=laptop-b COORDINATOR_URL=$${COORDINATOR_URL:?Set COORDINATOR_URL to Laptop A, for example http://192.168.1.20:8001} python3 -m client.clinical_worker

# --- Removes all generated files across every folder ---

clean:
	rm -f baseline/train.npz baseline/job.npz baseline/baseline_predictions.npz baseline/baseline_report.json
	rm -f shared/baseline_model.joblib
	rm -f client/job_part1.npz client/job_part2.npz client/results_part1.npz client/results_part2.npz
	rm -f train.npz job.npz baseline_model.joblib baseline_predictions.npz baseline_report.json job_part1.npz job_part2.npz results_part1.npz results_part2.npz
	@echo "Cleaned up generated files."