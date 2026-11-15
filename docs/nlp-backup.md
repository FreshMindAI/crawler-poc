# Local pretrained NLP backup

The baseline is locally executed YAKE plus versioned schema/content page-type
rules. YAKE is unsupervised keyword extraction, not a trained taxonomy model;
lower `raw_score` is better, not a confidence probability. Page types are
`product`, `article`, `category`, `other` or `unknown`.

Optional alternative: KeyBERT with a locally cached sentence-transformer such as
`sentence-transformers/all-MiniLM-L6-v2`. KeyBERT ranks candidate keyphrases using
document/phrase embedding similarity; it is not a substitute for validating the
page-type taxonomy. Both library and model must execute locally. No model was
downloaded or hosted inference called in this implementation.

Before enabling:

1. Review the exact model card/license, redistribution terms and artifact
   revision; pin the resolved commit/checksums. Do not claim a floating model name
   is reproducible. Source: https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2
2. Authorize artifact download separately; optional `.[nlp]` dependencies are not
   installed by the default locked environment. Source: https://maartengr.github.io/KeyBERT/
3. Use the same held-out human-reviewed corpus for YAKE and the alternative.
   Existing six synthetic cases are regression smoke tests, not sufficient
   model-selection evidence. Include product/article/category, mixed-language,
   sparse/challenge and noisy pages, with relevance judgments independent of the
   extraction algorithm.
4. Measure human precision@5/nDCG, page-type macro-F1 separately, abstention,
   cold-start/model-load/inference CPU, peak RSS, artifact size and batching.
   Preserve actual model outputs, annotations and revision with each result.
5. Promote only after a declared quality gain justifies resource/latency cost and
   no security/license regression. Retain the explainable fallback and version
   every classifier change. No unmeasured improvement is asserted here.
