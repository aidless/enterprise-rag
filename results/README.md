# results/

This directory holds the committed evaluation files:

- `hybrid_m1.json` — sparse fusion on 537 documents / 11994 chunks, with per-question rows
- `dense_m2.json` — bge-small-zh versus the sparse arm on the same questions
- `metamorphic_m3.json` — per-relation rows before and after the query normalizer

`make check` recounts the summaries from those rows. Prose elsewhere in the repository is not a second source of numbers. The sister corpus that produced these files is not stored here, so a fresh clone cannot re-index them.

The frozen 7-document baseline is re-run from `baseline/rag_demo.py`, not copied into an extra file in this directory.
