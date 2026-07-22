"""Transit satisfaction: NLP pipeline that scores public-transit-related text
for rider satisfaction, served as a small production-style API.

This package is a modernized rebuild of an earlier academic project
(tweet streaming + geo-tagging + fastText vectors + RandomForest classifier
+ MongoDB storage). The ML logic here is simplified to a TF-IDF + Logistic
Regression pipeline so the whole thing is reproducible without external
API keys or a live Twitter stream, while keeping the same shape: a trained
artifact, a clean serving layer, and a storage layer behind an interface.
"""

__version__ = "0.1.0"
