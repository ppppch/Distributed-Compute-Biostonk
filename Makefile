#Run first three steps with: make baseline
#Run an individual step with: make X , ex: make prepare

prepare:
	python3 prepare_dataset.py

train:
	python3 train_model.py

baseline_run:
	python3 run_baseline.py

worker1:
	python3 run_worker1.py

worker2:
	python3 run_worker2.py

split:
	python3 split_job.py

#Runs all three, in order, one after another
baseline: prepare train baseline_run
	@echo "Baseline pipeline complete."

#Splits then runs both workers
workers: split worker1 worker2
	@echo "Split, workers ran, computers simulated."

#Runs all
all: baseline workers

#Runs full pipeline including verification
demo: all
	python3 combine_and_verify.py

#Removes all the files that are generated
clean:
	rm -f train.npz job.npz baseline_model.joblib baseline_predictions.npz baseline_report.json job_part1.npz job_part2.npz results_part1.npz results_part2.npz
	@echo "Cleaned up generated files."