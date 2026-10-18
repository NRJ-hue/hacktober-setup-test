# Datasets & Benchmarks

## Current Datasets (Synthetic Only)

In accordance with strict repository size limits and copyright cleanliness, no proprietary contracts or third-party corpora are committed to this repository. All automated evaluations use carefully constructed synthetic documents:

1. **Synthetic Residential Lease Agreement** ([evaluate_agent.py](file:///c:/Users/nilab/hacktober-setup-test/scripts/evaluate_agent.py)):
   - 6 structured clauses covering rent obligations, security deposit return deadlines, termination notice periods, ambiguous repair timelines ("reasonable time"), assignment/subletting prohibitions, and utility allocations.
   - Includes adversarial prompt injection payloads embedded within clause text to test prompt boundary integrity.

2. **Synthetic 30-Page Commercial Services Agreement** ([test_30page_retrieval.py](file:///c:/Users/nilab/hacktober-setup-test/scripts/test_30page_retrieval.py)):
   - 30 distinct standard contract sections (Definitions, Payment Terms, Term & Termination, IP Ownership, Indemnity, Arbitration, Force Majeure, etc.).
   - Used to validate BM25 score scaling and the `MIN_SCORE = 0.5` evidence sufficiency threshold on multi-page documents.

## Optional External Benchmark: CUAD

For users wishing to run large-scale empirical benchmarks on real legal contracts, the pipeline is compatible with the **Contract Understanding Atticus Dataset (CUAD) v1**:

- **Source**: Atticus Project / Hugging Face (`atticus/cuad`)
- **License**: Creative Commons Attribution 4.0 International ([CC BY 4.0](https://creativecommons.org/licenses/by/4.0/))
- **Commit Status**: **Not committed to this repository**.
- **Usage**: To benchmark on CUAD:
  1. Download the CUAD dataset JSON from the official Atticus Project repository.
  2. Parse the contract text and ground-truth labeled spans into `EvidencePassage` objects.
  3. Run `validate_response()` against the labeled spans to compute extraction recall and precision.
