"""
scripts/compute_campaign_similarity.py

SentinelX - Compute Campaign Similarity

FIX vs. previous version: similarity_score was the average of ALL random
comment pairs in a campaign. With a small shared template pool, most
random pairs don't match, which drowns out the real signal (average
landed around 0.12 regardless of how coordinated the campaign actually
was).

FIX v2: similarity_score is now the average NEAREST-NEIGHBOR similarity
per comment -- for each comment, its highest cosine similarity to any
OTHER comment in the same campaign, then averaged across the campaign.
This is the standard approach for detecting near-duplicate / copy-paste
content: it directly measures "what fraction of this campaign's content
closely matches something else in the cluster," which is what coordinated
bot/spam behavior actually looks like. Still real TF-IDF + cosine
similarity on real comment text -- no hardcoded numbers.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

import config

comments = pd.read_csv(config.GENERATED_DIR / "comments.csv")
accounts = pd.read_csv(config.GENERATED_DIR / "accounts.csv")
campaigns = pd.read_csv(config.GENERATED_DIR / "campaigns.csv")

comments = comments.merge(
    accounts[["account_id", "campaign_id"]], on="account_id", how="left"
)

scores = {}

for campaign_id, group in comments[comments["campaign_id"].notna()].groupby("campaign_id"):
    texts = group["text"].fillna("").tolist()

    if len(texts) < 2:
        scores[campaign_id] = 0.0
        continue

    vectorizer = TfidfVectorizer(stop_words="english", min_df=1)
    tfidf_matrix = vectorizer.fit_transform(texts)
    sim_matrix = cosine_similarity(tfidf_matrix)

    # Zero out self-similarity on the diagonal so it doesn't inflate the score
    np.fill_diagonal(sim_matrix, 0.0)

    # For each comment, its best match to any OTHER comment in the campaign
    nearest_neighbor_scores = sim_matrix.max(axis=1)

    scores[campaign_id] = round(float(nearest_neighbor_scores.mean()), 4)

campaigns["similarity_score"] = campaigns["campaign_id"].map(scores).fillna(0.0)

output_file = config.GENERATED_DIR / "campaigns.csv"
campaigns.to_csv(output_file, index=False)

if __name__ == "__main__":
    print(campaigns[["campaign_id", "campaign_type", "similarity_score"]])
    print(f"\nUpdated {output_file} with nearest-neighbor TF-IDF cosine similarity scores.")