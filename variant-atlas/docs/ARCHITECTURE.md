# Variant Atlas: evidence before explanation

```mermaid
flowchart LR
    U[UniProt P60484] --> A[Immutable source assets + hashes]
    M[MaveDB activity and abundance] --> A
    P[RCSB experimental 1D5R] --> A
    A --> I[Identity, assay and mapping audits]
    I --> D[Versioned Parquet and scientific workspace]
    D --> B[FastAPI deterministic tools]
    B --> S[(Local locked store or configured Atlas)]
    S --> W[Leased job worker]
    W --> L[Model-selected bounded actions]
    L --> T[Scoped concurrent specialists]
    T --> C[Reconciliation and claim checks]
    C --> R[Research brief + unresolved hypotheses]
    S --> E[Persisted events / SSE]
    E --> F[Separate React frontend]
    D --> V[Authentic Mol* molecular view]
    V --> F
    F --> G[Task chamber / table / evidence / replay]
```

The model chooses work; deterministic tools decide eligibility, native-score calculations and whether coordinates support a distance. Persisted artifacts connect those decisions to the final output. A completed run means the bounded workflow ended with stated limitations; it does not prove its hypotheses.

```mermaid
flowchart TD
    Q[Research question + explicit criteria] --> J[Persist job and source versions]
    J --> K[Claim lease / inspect checkpoint]
    K --> A[Ask model for typed action]
    A -->|Tool| T[Validate scope / calculate / persist artifact]
    A -->|Delegate| S[Persist scoped task / run bounded worker]
    A -->|Revise| H[Record changed hypothesis and limitation]
    T --> A
    S --> A
    H --> A
    A -->|Finalize| V{Identity, comparability, mapping,
eligibility, reviews and claims checked?}
    V -->|Missing| X[Persist explicit revision-required artifact]
    X --> A
    V -->|Passed mechanical checks| R[Save reviewable brief with limitations]
    A -->|Budget / failure / cancellation| Z[Stop and preserve checkpoints]
```

Provider labels, scientific data labels, storage labels and playback labels remain separate. An OpenRouter run on authentic PTEN data is real scientific-data execution, but is not an Argon challenge submission. Local lexical retrieval is not Atlas hybrid search. A replay is recorded playback, not a running model.
