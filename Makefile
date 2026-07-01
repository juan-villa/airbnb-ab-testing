.PHONY: all clean-data simulate analyze dashboard

all: clean-data simulate analyze

clean-data:
	python3 src/clean_data.py

simulate:
	python3 src/simulate_experiment.py

analyze:
	python3 src/run_analysis.py

dashboard:
	streamlit run dashboard/app.py
