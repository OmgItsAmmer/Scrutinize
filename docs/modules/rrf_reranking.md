# RRF Reranking (Reciprocal Rank Fusion) & Hybrid Search

## 1. What are Dense and Sparse Vectors?

* **Dense Vectors (Semantic Similarity)**: Captures the conceptual meaning of text. 
  * *Example line*: `"Where is the checkout page?"` $\rightarrow$ Embedded into a 1536-dimensional array of floats: `[0.012, -0.045, ..., 0.123]`.
  * *Best for*: Synonyms, intent matching, and conceptual queries.
* **Sparse Vectors (Keyword/Lexical Similarity)**: Captures exact term matching (like BM25).
  * *Example line*: `"Where is the checkout page?"` $\rightarrow$ Key-value pairs of word indices and weights: `{"indices": [108, 982], "values": [0.55, 0.78]}` representing terms `checkout` and `page`.
  * *Best for*: Specific product codes, acronyms, exact phrases, and names.

---

## 2. How Reciprocal Rank Fusion (RRF) Works

Instead of comparing raw similarity scores (which are on different scales), RRF ranks documents based solely on their **position** (rank) in each search method's output.

For a document $d$, its RRF score is:

$$RRF\_Score(d) = \frac{1}{k + rank_{dense}(d)} + \frac{1}{k + rank_{sparse}(d)}$$

* $rank_{dense}(d)$ is the position (1-indexed) in the dense search results.
* $rank_{sparse}(d)$ is the position (1-indexed) in the sparse search results.
* $k$ is a constant hyperparameter (default: `60`) to smooth the scores.

---

## 3. Example of Chunk Ranking & Top-K Extraction

Suppose $k = 60$ and we query: `"API connection pooling"`

1. **Dense Search Results**:
   1. Chunk A (Rank 1)
   2. Chunk B (Rank 2)
   3. Chunk C (Rank 3)
2. **Sparse Search Results**:
   1. Chunk C (Rank 1)
   2. Chunk A (Rank 2)
   3. Chunk D (Rank 3)

**Calculated RRF Scores**:
* **Chunk A**: $\frac{1}{60 + 1} + \frac{1}{60 + 2} \approx 0.01639 + 0.01613 = 0.03252$
* **Chunk C**: $\frac{1}{60 + 3} + \frac{1}{60 + 1} \approx 0.01587 + 0.01639 = 0.03226$
* **Chunk B**: $\frac{1}{60 + 2} + 0 \approx 0.01613$
* **Chunk D**: $0 + \frac{1}{60 + 3} \approx 0.01587$

**Final Ranking (Sorted descending)**:
1. **Chunk A** ($0.03252$)
2. **Chunk C** ($0.03226$)
3. **Chunk B** ($0.01613$)
4. **Chunk D** ($0.01587$)

**Top-K Extraction**: If $K = 2$, we slice the sorted list to return the top 2 elements (**Chunk A** and **Chunk C**).

---

## 4. Pros & Cons

### Pros
* **Out-of-the-Box Precision**: Combines the best of conceptual understanding and exact term matches.
* **No Score Scaling Needed**: Solves the issue of merging two mathematically incomparable similarity scores.
* **Zero Model Calibration**: Unlike machine-learned cross-encoders, it requires no training or dataset tuning.

### Cons
* **Double Storage/Computation**: Qdrant stores both dense and sparse indices, increasing database size.
* **Cold Starts**: Generating sparse vectors on query time adds a minor CPU cost (~2-5ms).
