# Model decisions: what the original project tried, and why this rebuild chose differently

This is the write-up a software engineer would hand to (or receive from) a
data science team before productionizing a model: what was tried, what got
shipped, and why -- so the choice can be revisited on evidence later instead
of re-litigated from scratch.

## What the original project actually tried

The original repo explored three different approaches to scoring a tweet's
sentiment, side by side, without settling on one:

1. **`sentiment_analysis.py` -- TextBlob polarity.** No training at all:
   `TextBlob(tweet).sentiment.polarity`, rescaled through a hand-written
   `result_cal` function into a rough -1..1 score. Zero setup cost, but a
   generic English-sentiment lexicon has no notion of what "on time,"
   "overcrowded," or "fare hike" mean *for transit specifically* -- it
   would score "the bus was involved in a serious incident" and "the bus
   fare increased" as similarly negative for unrelated reasons.

2. **`convert_to_vec.py` + `applying_ML_algorithms.py` -- word2vec/fastText
   vectors -> `RandomForestClassifier`.** Tweets tokenized (custom regex
   handling emoticons, hashtags, mentions, URLs), embedded into 300-dimension
   vectors, averaged, fed into a random forest evaluated by F1/ROC-AUC. A
   real step up in modeling power over TextBlob, at the cost of needing a
   pretrained word2vec/fastText model file (hundreds of MB to GBs) present
   at both train *and* serve time, and losing interpretability -- "why did
   the forest score this 0.3" is a much harder question than "why did
   logistic regression weight these tokens negatively."

3. **`CLASSIFICATION_SENTIMENT.py` -- GloVe embeddings -> Keras
   Bidirectional LSTM/GRU.** The heaviest approach: a 200-dimension GloVe
   embedding file, several recurrent layers, trained with Keras/TensorFlow.
   Likely the highest ceiling of the three on a large enough labeled
   dataset, but the original script hardcodes local Windows file paths to
   the embedding file and training CSV, has no train/serve contract at all,
   and needs a GPU to train in reasonable time -- none of which is
   reproducible by cloning the repo.

None of the three approaches got the same treatment: no shared evaluation
harness, no versioned artifact, no test suite, and (per `HANDOFF.md`) a
real credential leak in the DB layer alongside all of it.

**Correction, found after reading `main.py`/`Streamer.py` in full:** the
three approaches were not tried "side by side" as equally-weighted
experiments. `main.py` runs three threads forever -- ingestion
(`Streamer.py`), hourly consolidation + geo-tagging (`save_csv_file.py`),
and a classification thread that calls `CLASSIFICATION_SENTIMENT.main()`
directly. **The GloVe+LSTM model was the one actually wired into the live
pipeline.** `applying_ML_algorithms.py` (word2vec+RandomForest) and
`sentiment_analysis.py` (TextBlob) were separate offline experiments,
invoked only from `post_existing_file.py`/`straight_analysis.py` to
reprocess already-saved files -- never part of the live streaming path.
That changes the honest framing below: this rebuild's TF-IDF+LogisticRegression
is a deliberate simplification *from what was actually shipped*, not just
a pick among three untested equals.

## What this rebuild chose, and why

`train.py` uses **TF-IDF (1-2 grams) + `LogisticRegression`** inside a single
`sklearn.Pipeline`. That choice was made on these grounds, not by default:

- **Reproducibility.** `pip install -r requirements.txt && make train` runs
  end-to-end on a laptop in under a second, no GPU, no multi-GB embedding
  download, no external model file to keep in sync between training and
  serving. Anyone who clones this repo gets the exact same artifact.
- **Interpretability.** TF-IDF + logistic regression has inspectable
  per-token weights -- if a data science team asks "why is this text scored
  unsatisfied," the answer is a short list of weighted n-grams, not "ask the
  random forest" or "ask the LSTM's hidden state."
- **A real train/serve contract.** `train.py` owns every modeling decision
  and produces exactly one artifact (`model.pkl` + `model.metrics.json`,
  the latter now also recording `sklearn_version` for reproducibility
  provenance); `predict.py` and the API only ever call `.predict_proba` on
  a fitted sklearn-compatible pipeline. None of the three original
  approaches had anything like this -- swapping the vectorizer/classifier
  inside `train.py` (including to word2vec+RandomForest or a small
  transformer) requires zero changes to `predict.py`, the API, or the
  tests, *as long as the swapped-in pipeline still exposes
  `.predict_proba`.*

**This is a deliberately boring choice given a small, synthetic training
set** (`ml/data/sample_tweets.csv`, hand-written sentences -- the original's
real historical tweet data was never available to this rebuild). The
accuracy ceiling of TF-IDF + logistic regression on a bigger, real,
transit-specific labeled dataset would very plausibly be lower than a
properly-tuned word2vec/RandomForest or transformer approach. That's the
honest tradeoff: this rebuild optimizes for "anyone can run this end to end
and trust the number," not for maximum possible F1 on data nobody else can
access.

## How a data science team would evolve this

The natural next step to raise the accuracy ceiling -- if/when real labeled
transit-tweet data exists -- is entirely inside `train.py`:
swap in fastText embeddings or a small transformer, keep evaluating with
the same F1/ROC-AUC/cross-val harness already in `TrainingMetrics`, and
ship a new `model.pkl` through the exact same serving path. A model
registry (MLflow, mentioned in the README's "what I'd do with more time")
is the natural place to version and compare candidates once there's more
than one artifact worth keeping around -- but the artifact *contract*
(`.predict_proba` on a fitted sklearn-compatible pipeline) is what makes
that swap safe regardless of which specific model ends up on the other side
of it.
