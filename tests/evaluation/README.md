# Evaluation Scripts

## Reranking Quality Evaluation

### Quick Start

```bash
# Run evaluation on staging
python tests/evaluation/measure_reranking_quality.py

# Save results
python tests/evaluation/measure_reranking_quality.py --save staging_results.json

# Create baseline (before improvements)
python tests/evaluation/measure_reranking_quality.py --create-baseline

# Compare to baseline (after improvements)
python tests/evaluation/measure_reranking_quality.py --baseline
```

### Golden Dataset

**Location**: `tests/evaluation/golden_queries.json`

**Queries**: 15 diverse legal queries covering:
- Employment law (5 queries)
- Constitutional rights (3 queries)
- Company law (2 queries)
- Contract law (1 query)
- Court procedures (1 query)
- Property law (1 query)
- General rights (2 queries)

**Complexity Distribution**:
- Simple: 5 queries
- Moderate: 8 queries
- Complex: 2 queries

### Metrics Calculated

1. **Precision@5**: Relevant topics in top 5 results
2. **Precision@10**: Relevant topics in top 10 results
3. **Doc Type Match**: How well doc types match expected
4. **Rerank Method**: Which method was used (cross-encoder vs fallback)

### Expected Results

**Baseline** (before reranking fix):
- Precision@5: ~0.52
- Precision@10: ~0.68

**With Cross-Encoder**:
- Precision@5: ~0.65-0.75 (+15-30%)
- Precision@10: ~0.75-0.85 (+10-20%)

### Usage Examples

```bash
# 1. Create baseline (on old code)
git checkout main  # Old code
python tests/evaluation/measure_reranking_quality.py --create-baseline

# 2. Measure improvements (on new code)
git checkout fix/crossencoder-reranking  # New code
python tests/evaluation/measure_reranking_quality.py --baseline --save new_results.json

# 3. View detailed results
cat new_results.json | jq '.details[] | {query, precision_at_5, rerank_method}'
```

### Troubleshooting

**Issue**: "No module named 'api'"
- **Solution**: Run from project root with venv activated

**Issue**: "Golden dataset not found"
- **Solution**: Ensure `golden_queries.json` exists in same directory

**Issue**: "Orchestrator initialization failed"
- **Solution**: Check environment variables (MILVUS_ENDPOINT, R2_*, etc.)

### Adding More Golden Queries

Edit `golden_queries.json` and add:

```json
{
  "id": "unique_id",
  "query": "Your legal query here",
  "expected_topics": ["topic1", "topic2"],
  "expected_doc_types": ["act", "constitution"],
  "complexity": "simple|moderate|complex",
  "min_precision": 0.6
}
```

---

**Created**: 2024-09-30  
**Last Updated**: 2024-09-30
