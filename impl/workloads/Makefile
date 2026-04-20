PYTHON      ?= python3

CAPTURED_DIR    := captured/periodic_suppression
SYNTHESIZED_DIR := synthesized/duty_bias

CAPTURED_SRC    := captured/source/verified_per_period.csv

TOOLS := tools

.PHONY: all captured synthesized validate clean

all: captured synthesized validate

captured: $(CAPTURED_DIR)/witness.csv

$(CAPTURED_DIR)/witness.csv: $(TOOLS)/convert_digital_csv.py $(CAPTURED_SRC)
	$(PYTHON) $(TOOLS)/convert_digital_csv.py \
	  --input $(CAPTURED_SRC) \
	  --out $(CAPTURED_DIR) \
	  --period-ns 50000 \
	  --config-id 1

synthesized: $(SYNTHESIZED_DIR)/witness.csv

$(SYNTHESIZED_DIR)/witness.csv: $(TOOLS)/synthesize_duty_bias.py
	$(PYTHON) $(TOOLS)/synthesize_duty_bias.py \
	  --out $(SYNTHESIZED_DIR) \
	  --periods 20000 \
	  --period-ns 100000 \
	  --bias-pct 15.0 \
	  --config-id 2

validate: captured synthesized
	$(PYTHON) $(TOOLS)/validate_workload.py $(CAPTURED_DIR)
	$(PYTHON) $(TOOLS)/validate_workload.py $(SYNTHESIZED_DIR)

clean:
	rm -f $(CAPTURED_DIR)/witness.csv $(CAPTURED_DIR)/evidence.csv $(CAPTURED_DIR)/PROVENANCE
	rm -f $(SYNTHESIZED_DIR)/witness.csv $(SYNTHESIZED_DIR)/evidence.csv $(SYNTHESIZED_DIR)/PROVENANCE
