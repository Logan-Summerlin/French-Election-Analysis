# Leading candidate by income and education — 2002 and 2022

These four figures reproduce an Economist-style candidate-winner landscape for
the first round of the French presidential elections in 2002 and 2022.

## Figures

- `leading_candidate_income_education_2002_full.png`
- `leading_candidate_income_education_2002_central90.png`
- `leading_candidate_income_education_2022_full.png`
- `leading_candidate_income_education_2022_central90.png`

The **full** version uses every matched metropolitan-France precinct with at
least 50 valid first-round votes. The **central90** version independently finds
the 5th and 95th percentiles of median income and higher-education share, then
drops any precinct outside either interval and rescales both axes to the retained
sample.

## How the background is calculated

At every point on a regular income–education grid, the script:

1. standardises median income and higher-education share within the plotted
   sample;
2. finds the 100 nearest precincts in that two-dimensional space;
3. takes each candidate's mean first-round vote share across those precincts;
4. colours the cell for the candidate with the highest mean.

Black dots show the underlying precincts. Direct labels are placed in candidates'
largest substantial regions; the legend lists every candidate that wins at least
one grid cell.

## Data and interpretation

Election results are Ministry of the Interior bureau-de-vote results distributed
through data.gouv.fr. Socioeconomic attributes come from INSEE:

- **2002 election → 2012 income and education.** Filosofi begins in 2012, so this
  is the earliest available commune-level median disposable-income measure and
  matches the repository's existing 2002–2022 comparison convention.
- **2022 election → 2021 income and education.** This is the nearest available
  pre-election census/Filosofi vintage.

The election result is precinct-level, but income and education are measured at
the commune level and attached to each precinct in that commune. These charts
therefore describe ecological relationships and should not be interpreted as
individual-level voting behaviour.

## Reproduce

```bash
python3 -m pip install -r requirements-candidate-landscapes.txt
python3 analysis/candidate_landscape_income_education.py
```

The first run downloads roughly 270 MB of source archives. Downloaded and
processed data remain under gitignored locations; the four PNGs and
`build_summary.csv` are committed outputs.
