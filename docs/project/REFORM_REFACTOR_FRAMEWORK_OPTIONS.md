# Future Refactor – Framework Options and Migration Path

> **Context**  
> After MVP launch we plan to simplify and harden the code-base by replacing bespoke orchestration, retrieval and pipeline code with higher-level, production-ready frameworks.

---

## 1. Orchestration / Agent Frameworks

| Candidate | Drops / Replaces | Key Gains |
|-----------|-----------------|-----------|
| **LangGraph DSL** (continue) | Hand-rolled `StateGraph` plumbing | Built-in retries, timeouts, checkpointing, streaming, tracing |
| **LlamaIndex RouterQueryEngine** | `_route_intent`, custom nodes | Declarative intent routing, hybrid retrieval, fewer lines |
| **Haystack v2 Pipelines** | Most orchestrator code & FastAPI glue | YAML DAGs, built-in REST API, evaluations |
| **Semantic-Kernel (Planner/Functions)** | If we need .NET cross-lang | Skill-composition, multi-modal future-proofing |

## 2. Retrieval Layer

| Candidate | Replaces | Extras |
|-----------|----------|--------|
| **LlamaIndex HybridRetriever** | `RetrievalEngine`, BM25 merge logic | One-liner Milvus + BM25, filters, caching |
| **Vespa / Weaviate Hybrid** | Separate sparse/ vector stores | Native hybrid scoring, one endpoint |
| **Elastic 8 Sparse+Dense** | BM25 pickle + Milvus | Single infra stack, prefix filters |

## 3. Data / Pipeline

* **Dagster / Prefect** for ETL (parse → chunk → embed → upsert).  
  *Lineage, retries, alerting.*
* **LlamaIndex Ingestion Pipelines** – declarative transforms.
* **DVC / LakeFS** for versioned R2 corpus.

## 4. Serving & Deployment

* **LangServe** or **LlamaIndex Server** – turn a `Runnable` into FastAPI/SSE with 20 LOC.
* **BentoML / Modal / Ray Serve** – autoscaling, GPU scheduling.

## 5. Observability & Evaluation

* **LangSmith datasets + evals** – regression tests in CI.  
* **TruLens-Eval** – grounding, toxicity scores.
* **OpenTelemetry** – traces + metrics into Grafana.

## 6. Prompt & Tool Management

* **PromptLayer / Guidance** – versioned prompts, Jinja2-style templates.
* **LlamaIndex StructuredTool** + Pydantic – typed tool IO.

## 7. Config & Secrets

* `pydantic.BaseSettings` v2 + **Doppler / AWS Secrets Manager** – kill `.env.local` leakage.

## 8. Testing & CI

* `pytest-langchain` fixtures, LangSmith rubric tests.  
* Data validation with **Great Expectations** or **DLT**.

## 9. Performance Ideas

* **LanceDB / Chroma** for local dev vectors.
* Embedding cache via LlamaIndex `ServiceContext`.

---

### Suggested Migration Phases

1. **Retrieval swap** – Integrate LlamaIndex HybridRetriever, keep FastAPI.  
2. **Serve with LangServe** – replace custom routers.  
3. **Dagster pipeline** – move all R2 scripts into a scheduled job.  
4. **Observability** – LangSmith eval data set & OpenTelemetry.  
5. **Prompt management & tests** – Guidance + rubric tests.  
6. **Full orchestration refactor** – RouterQueryEngine or Haystack once stable.

*Document generated after MVP build (2025-09-21) for future refactor planning.*
