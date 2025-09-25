# Article A Experiment Suite

## Objectives
- Reproduce the simulations required for the "Article A" study of the MNE3SD campaign.
- Provide a single location for scenario definitions and reusable utilities shared across the study.
- Collect per-scenario metrics as CSV files and post-process them into publication-ready figures.

## Common simulation parameters
Every scenario script exposes a consistent set of command line flags so experiments can be reproduced easily:

- `--config`: Path to an optional simulation configuration file overriding the defaults shipped with the repository.
- `--seed`: Base random seed applied to the simulator. Individual scripts may derive additional seeds from this value.
- `--runs`: Number of Monte Carlo repetitions to execute for each scenario configuration.
- `--duration`: Simulation duration in seconds. When omitted, each script falls back to its documented default.
- `--output`: Target CSV file. By convention this is placed inside `results/mne3sd/article_a/`.

Scripts under `plots/` share an analogous interface:

- `--input`: One or more CSV files produced by the scenario scripts.
- `--figures-dir`: Directory where the generated figures will be written. Defaults to `figures/mne3sd/article_a/`.
- `--format`: Image format for the exported charts (e.g. `png`, `pdf`, `svg`).

### Execution profiles
All scenario launchers accept the shared `--profile` flag (or the `MNE3SD_PROFILE`
environment variable) to switch between presets:

- `full` *(default)* – preserves the publication-grade parameters documented
  in each script.
- `ci` – reduces node counts, repetitions and explored parameter sets to keep
  automated checks and quick smoke tests fast while still exercising the
  complete pipeline.

## Directory layout and artefacts
```
scripts/mne3sd/article_a/
├── README.md                # This guide
├── __init__.py              # Package marker for shared helpers
├── scenarios/               # Data generation entry points
│   └── __init__.py
└── plots/                   # Figure generation entry points
    └── __init__.py
```

### CSV outputs
All raw and aggregated metrics produced by the experiments must be stored under `results/mne3sd/article_a/`. Each scenario script should create a dedicated subfolder when writing multiple files, e.g. `results/mne3sd/article_a/urban/summary.csv`. Shared preprocessing utilities can also persist intermediate CSV files in the same tree.

### Figures
Use `figures/mne3sd/article_a/` to store any figure exported for Article A. Prefer descriptive file names that match the manuscript, for example `figure_2_packet_delivery.pdf`. Intermediate artefacts (such as debugging plots) can live in a dedicated subdirectory that is ignored when composing the final paper.

## Running the scripts
All commands below are meant to be executed from the repository root. Replace placeholders surrounded by angle brackets with scenario-specific values.

### Generate simulation data
```
python -m scripts.mne3sd.article_a.scenarios.<scenario_module> \
    --runs 10 \
    --duration 3600 \
    --seed 42 \
    --output results/mne3sd/article_a/<scenario_name>.csv
```

Each scenario module can accept additional flags (for example to tweak topology, traffic profiles, or PHY parameters). Document any scenario-specific options directly inside the script docstring.

### Generate figures
```
python -m scripts.mne3sd.article_a.plots.<figure_module> \
    --input results/mne3sd/article_a/<scenario_name>.csv \
    --figures-dir figures/mne3sd/article_a/ \
    --format pdf
```

Plot modules can aggregate multiple CSV files by repeating the `--input` flag. Use descriptive module names such as `throughput_breakdown` or `sensitivity_overview` to keep the documentation aligned with the paper structure.

## Reproducing the full pipeline
To run the complete workflow end-to-end:

1. Execute all required scenario modules to populate `results/mne3sd/article_a/`.
2. Verify the generated CSV files and optionally commit them in a separate branch if they should be version-controlled.
3. Launch each plotting module to populate `figures/mne3sd/article_a/`.
4. Review the figure files locally before exporting them to the manuscript repository.

### Batch execution helper

To execute the complete Article A pipeline in one step, use the shared launcher located at `scripts/mne3sd/run_all_article_outputs.py`:

```
python -m scripts.mne3sd.run_all_article_outputs --article a
```

The script runs all `run_class_*` scenarios followed by the available `plot_*` modules and prints a summary of the generated CSV files and figures. Use `--skip-scenarios` or `--skip-plots` to limit the execution to one stage, for example when you only need to refresh the figures from previously generated data.

Keep this README updated as new scenarios or plots are added to guarantee consistent usage across collaborators.
