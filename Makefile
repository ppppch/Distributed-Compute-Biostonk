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

# --- Removes all generated files across every folder ---

clean:
	rm -f baseline/train.npz baseline/job.npz baseline/baseline_predictions.npz baseline/baseline_report.json
	rm -f shared/baseline_model.joblib
	rm -f client/job_part1.npz client/job_part2.npz client/results_part1.npz client/results_part2.npz
	@echo "Cleaned up generated files."