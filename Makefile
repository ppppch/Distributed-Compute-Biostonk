#Run first three steps with: make baseline
#Run an individual step with: make X , ex: make prepare

prepare:
	python3 prepare_dataset.py

train:
	python3 train_model.py

baseline_run:
	python3 run_baseline.py

#Runs all three, in order, one after another
baseline: prepare train baseline_run
	@echo "Baseline pipeline complete."

#Removes all the files that are generated
clean:
	rm -f train.npz job.npz baseline_model.joblib baseline_predictions.npz baseline_report.json
	@echo "Cleaned up generated files."