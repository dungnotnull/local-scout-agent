"""Benchmark script for HuggingFace model inference latency.

Usage: python scripts/benchmark_models.py
"""
import time
import sys


MODELS = [
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    "cardiffnlp/twitter-xlm-roberta-base-sentiment-multilingual",
    "facebook/nllb-200-distilled-600M",
    "dslim/bert-base-NER",
    "microsoft/Phi-3-mini-4k-instruct",
]


def benchmark_model(model_id: str) -> dict:
    return {
        "model_id": model_id,
        "load_time_ms": None,
        "inference_time_ms": None,
        "memory_mb": None,
        "status": "not_run",
    }


def run_benchmarks():
    results = []
    for model_id in MODELS:
        result = benchmark_model(model_id)
        results.append(result)

    print("\nBenchmark Results:")
    print("-" * 80)
    for r in results:
        print(f"  {r['model_id']}: {r['status']}")
    print("-" * 80)

    return results


if __name__ == "__main__":
    run_benchmarks()
