TARGET := main
SRC := $(wildcard src/*.tex)
TOOLS := tools/paper_plots.py
METRICS := ../impl/results/gem5/matrix_full/metrics.csv
PLOT_FIGS := figures/paper_main_results.pdf figures/paper_workload_sensitivity.pdf
SVG_SRC := figures/witness_evidence_arch_print.svg
SVG_PDF := figures/witness_evidence_conformance_arch.pdf

.PHONY: all clean plots

all: $(PLOT_FIGS) $(SVG_PDF) $(TARGET).pdf

plots: $(PLOT_FIGS)

$(PLOT_FIGS): $(TOOLS) $(METRICS)
	mkdir -p .mpl-cache .cache/fontconfig
	MPLCONFIGDIR=.mpl-cache XDG_CACHE_HOME=.cache \
	python3 tools/paper_plots.py --metrics $(METRICS) --outdir figures

$(SVG_PDF): $(SVG_SRC)
	rsvg-convert -f pdf -o $@ $<

$(TARGET).pdf: $(TARGET).tex $(SRC) references.bib usenix.sty $(PLOT_FIGS) $(SVG_PDF)
	pdflatex $(TARGET)
	bibtex $(TARGET)
	pdflatex $(TARGET)
	pdflatex $(TARGET)

clean:
	rm -f $(TARGET).aux $(TARGET).bbl $(TARGET).blg $(TARGET).log \
	      $(TARGET).out $(TARGET).pdf
	rm -f figures/paper_main_results.pdf figures/paper_main_results.png \
	      figures/paper_workload_sensitivity.pdf \
	      figures/paper_workload_sensitivity.png \
	      figures/witness_evidence_conformance_arch.pdf
	rm -rf .mpl-cache .cache
