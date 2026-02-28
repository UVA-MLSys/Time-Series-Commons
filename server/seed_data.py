#!/usr/bin/env python3
"""
seed_data.py — One-time (idempotent) migration from data/models.json → Cloud SQL.

Populates:
  - datasets table  (815+ rows, one per time series dataset)
  - models   table  (79 rows, one per benchmark / foundation model)

Usage (from repo root, with .env or environment variable set):
    cd /path/to/Time-Series-Commons
    DB_CONN_STR="postgresql://ts_user:PASSWORD@127.0.0.1:5432/timeseries_db" \
        python server/seed_data.py

    # or with a .env file in server/listener/:
    source server/listener/.env && python server/seed_data.py

Safe to re-run — uses ON CONFLICT (name) DO UPDATE everywhere.
"""

import json
import os
import sys
import logging
from pathlib import Path

try:
    import psycopg2
    from psycopg2.extras import Json, execute_batch
except ImportError:
    print("psycopg2-binary not installed. Run: pip install psycopg2-binary")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).parent.parent
MODELS_JSON = REPO_ROOT / "data" / "models.json"

# ---------------------------------------------------------------------------
# Model catalog — mirrors ALL_MODELS and getModelDescription() in js/models.js
# ---------------------------------------------------------------------------

ALL_MODELS = [
    'Informer', 'Monash TSER', 'UTSD', 'AutoGluon', 'Darts', 'TSLib',
    'TSFM-Granite', 'TSFM-Core', 'TSFM-Bench', 'LOTSA', 'Prophet',
    'NeuralForecast', 'Merlion', 'Aeon', 'DataLoop', 'NonUCR-UCI',
    'UCR', 'UEA', 'MONSTER', 'Monash', 'Monash-Common', 'Monash-small',
    'M1', 'M2', 'M3', 'M4', 'M5', 'M6',
    'TSB-UAD MOMENT', 'TSB-UAD Full', 'Hackernoon', 'Monash Moment',
    'Kaggle TS', 'FastML', 'Time-LLM', 'AutoTimes', 'ST-LLM',
    'LLM-Time', 'LLM-Mixer', 'LLM-prompt', 'LLM-PS', 'One Fits All',
    'Lag-Llama', 'Chronos-Pre', 'Chronos-Eval1', 'Chronos-Eval2',
    'ChronosBolt-Pre', 'ChronosBolt-Eval1', 'ChronosBolt-Eval2',
    'ChronosX-Eval2', 'ChronosX-Synth', 'ChronosX-Pre', 'ChronosX-Eval1',
    'TS-RAGZSEval', 'TS-RAGPreT', 'Tempo', 'TimeBench', 'InstructTime',
    'LPTM-Pre', 'LPTM-Eval', 'TS2Vec-Bench', 'TS2Vec-PreT', 'Automixer',
    'TTM-PreT', 'TTM-Eval', 'TTM-Bench', 'TSMamba-ZS', 'TSMamba-FullShot',
    'TimeGPT', 'GHPT', 'TimesNet', 'TimesFM', 'Time-MOE', 'Timer-XL',
    'LightGTS', 'CiK', 'NSF HDR', 'MLCommons-EQ',
]

# Inferred architecture labels for the models table.
# "Library/Benchmark" covers archives, competitions, and multi-algorithm toolkits.
MODEL_ARCHITECTURES = {
    'Informer':           'Transformer',
    'Monash TSER':        'Library/Benchmark',
    'UTSD':               'Library/Benchmark',
    'AutoGluon':          'AutoML',
    'Darts':              'Library/Benchmark',
    'TSLib':              'Library/Benchmark',
    'TSFM-Granite':       'Transformer',
    'TSFM-Core':          'Transformer',
    'TSFM-Bench':         'Library/Benchmark',
    'LOTSA':              'Library/Benchmark',
    'Prophet':            'Additive Decomposition',
    'NeuralForecast':     'Library/Benchmark',
    'Merlion':            'Library/Benchmark',
    'Aeon':               'Library/Benchmark',
    'DataLoop':           'Library/Benchmark',
    'NonUCR-UCI':         'Library/Benchmark',
    'UCR':                'Library/Benchmark',
    'UEA':                'Library/Benchmark',
    'MONSTER':            'Library/Benchmark',
    'Monash':             'Library/Benchmark',
    'Monash-Common':      'Library/Benchmark',
    'Monash-small':       'Library/Benchmark',
    'M1':                 'Statistical',
    'M2':                 'Statistical',
    'M3':                 'Statistical',
    'M4':                 'Ensemble',
    'M5':                 'Gradient Boosting',
    'M6':                 'Ensemble',
    'TSB-UAD MOMENT':     'Transformer',
    'TSB-UAD Full':       'Library/Benchmark',
    'Hackernoon':         'Library/Benchmark',
    'Monash Moment':      'Library/Benchmark',
    'Kaggle TS':          'Library/Benchmark',
    'FastML':             'Library/Benchmark',
    'Time-LLM':           'LLM',
    'AutoTimes':          'LLM',
    'ST-LLM':             'LLM',
    'LLM-Time':           'LLM',
    'LLM-Mixer':          'LLM',
    'LLM-prompt':         'LLM',
    'LLM-PS':             'LLM',
    'One Fits All':       'LLM',
    'Lag-Llama':          'Transformer',
    'Chronos-Pre':        'Transformer',
    'Chronos-Eval1':      'Transformer',
    'Chronos-Eval2':      'Transformer',
    'ChronosBolt-Pre':    'Transformer',
    'ChronosBolt-Eval1':  'Transformer',
    'ChronosBolt-Eval2':  'Transformer',
    'ChronosX-Eval2':     'Transformer',
    'ChronosX-Synth':     'Transformer',
    'ChronosX-Pre':       'Transformer',
    'ChronosX-Eval1':     'Transformer',
    'TS-RAGZSEval':       'RAG',
    'TS-RAGPreT':         'RAG',
    'Tempo':              'Transformer',
    'TimeBench':          'Library/Benchmark',
    'InstructTime':       'LLM',
    'LPTM-Pre':           'Transformer',
    'LPTM-Eval':          'Transformer',
    'TS2Vec-Bench':       'Contrastive',
    'TS2Vec-PreT':        'Contrastive',
    'Automixer':          'MLP',
    'TTM-PreT':           'MLP',
    'TTM-Eval':           'MLP',
    'TTM-Bench':          'MLP',
    'TSMamba-ZS':         'SSM',
    'TSMamba-FullShot':   'SSM',
    'TimeGPT':            'Transformer',
    'GHPT':               'Transformer',
    'TimesNet':           'CNN',
    'TimesFM':            'Transformer',
    'Time-MOE':           'SSM',
    'Timer-XL':           'Transformer',
    'LightGTS':           'GNN',
    'CiK':                'Library/Benchmark',
    'NSF HDR':            'Library/Benchmark',
    'MLCommons-EQ':       'Library/Benchmark',
}

MODEL_DESCRIPTIONS = {
    'Darts': 'Darts (Data Analysis and Real-Time Systems) is a Python library for time series forecasting developed by Unit8. It offers a unified interface for multiple forecasting models including statistical methods (ARIMA, ETS), machine learning approaches (Random Forests, LightGBM), and deep learning models (N-BEATS, Transformer). Darts supports both univariate and multivariate forecasting, handles covariates, and provides probabilistic forecasting capabilities with confidence intervals.',
    'Merlion': 'Merlion is a Python library for time series intelligence developed by Salesforce Research. It provides a unified interface for time series forecasting, anomaly detection, and change point detection. Merlion includes implementations of state-of-the-art algorithms including ARIMA, Prophet, LSTM, Transformer models, and ensemble methods. It emphasizes production-ready deployment with automatic hyperparameter tuning and model selection.',
    'Aeon': 'Aeon (formerly sktime) is a scikit-learn compatible Python toolkit for time series analysis. It provides a comprehensive suite of algorithms for time series classification, regression, clustering, and annotation. Aeon includes distance-based methods, shapelet transforms, dictionary-based approaches, and deep learning models. It emphasizes composability and modularity, allowing users to build complex pipelines.',
    'TSLib': 'TSLib (Time Series Library) is a comprehensive toolkit providing implementations of state-of-the-art time series forecasting models. It includes classic methods, modern deep learning approaches, and recent transformer-based architectures. TSLib emphasizes reproducible research with standardized experimental protocols and is widely used for benchmarking new forecasting methods.',
    'AutoGluon': 'AutoGluon-TimeSeries is an AutoML toolkit that automatically trains and ensembles multiple forecasting models. Developed by Amazon, it simplifies time series forecasting by automating model selection, hyperparameter tuning, and ensemble construction. AutoGluon combines statistical models (ETS, ARIMA), tree-based methods (CatBoost, LightGBM), and deep learning approaches for best-in-class performance.',
    'NeuralForecast': "NeuralForecast is Nixtla's deep learning library for time series forecasting. It provides scalable neural architectures (NHITS, NBEATS, TFT, DeepAR, Transformer) with a simple scikit-learn-style API. NeuralForecast supports probabilistic forecasting, automatic hyperparameter optimization, and efficient training on large datasets.",
    'Prophet': "Prophet is Meta's open-source forecasting tool based on additive decomposition of trend, seasonality, and holiday effects. Designed for business time series with strong seasonal patterns, it handles missing data and outliers robustly and requires minimal manual tuning, making it widely adopted in industry.",
    'UCR': 'The UCR Time Series Classification Archive is the largest public repository of time series classification datasets. Maintained by the University of California, Riverside, it has been the standard benchmark for evaluating time series classification algorithms since 2002, covering diverse domains from medical to industrial applications.',
    'UEA': 'The UEA Time Series Classification Archive extends UCR to multivariate time series. Maintained by the University of East Anglia, it provides multi-channel benchmark datasets for evaluating methods that exploit cross-dimensional relationships in classification tasks.',
    'NonUCR-UCI': 'NonUCR-UCI refers to time series datasets from the UCI Machine Learning Repository that are not part of the standard UCR archive. These datasets provide additional benchmark coverage across classification and regression tasks not captured by the UCR collection.',
    'Monash': 'The Monash Time Series Forecasting Archive is a comprehensive collection of real-world forecasting datasets from diverse domains. Maintained by Monash University, it standardizes evaluation protocols for both short- and long-term forecasting with datasets spanning energy, economic, demographic, and environmental domains.',
    'Monash TSER': 'Monash TSER (Time Series Extrinsic Regression) is an archive focused on regression tasks over time series. Unlike classification archives, TSER targets continuous target prediction from time series inputs across domains such as healthcare, energy, and materials science.',
    'Monash-Common': 'Monash-Common is a curated subset of the Monash Forecasting Archive containing the most widely cited and representative datasets for standardized model comparison. It provides a common ground for fair evaluation across different forecasting libraries.',
    'Monash-small': 'Monash-small is a compact subset of the Monash archive designed for rapid prototyping and lightweight benchmarking. It retains domain diversity while reducing computational overhead for model development and evaluation cycles.',
    'Monash Moment': 'Monash Moment refers to datasets from the Monash archive specifically used in the MOMENT foundation model evaluation suite. It provides a shared benchmark for comparing pre-trained time series models on real-world forecasting tasks.',
    'MONSTER': 'MONSTER (Multivariate tONe, Scalability, and TimE seRies) is a large-scale benchmark suite for time series classification evaluating models on datasets that stress scalability, multivariate structure, and diverse temporal patterns simultaneously.',
    'UTSD': 'UTSD (Unified Time Series Dataset) is a large-scale collection aggregating diverse public time series datasets into a unified format for pre-training and benchmarking foundation models. It covers multiple domains and temporal granularities to assess generalization capability.',
    'M1': 'M1 Competition (1982) was the first Makridakis forecasting competition, evaluating statistical and judgmental methods on 1,001 economic and business time series. Its findings challenged the dominance of complex models and established benchmarking standards for the field.',
    'M2': 'M2 Competition (1993) extended the M1 study with a focus on real-time updating and tracking signals. It evaluated 29 methods on monthly, quarterly, and yearly economic data, reinforcing insights about the value of simple statistical methods.',
    'M3': 'M3 Competition (2000) is the most widely cited forecasting competition, covering 3,003 time series across economic, industry, finance, and demographic domains. Its results strongly influenced practice and highlighted the robustness of simple benchmarks like Theta and exponential smoothing.',
    'M4': 'M4 Competition (2018) evaluated 60 methods on 100,000 time series from six frequencies. It was won by a hybrid Exponential Smoothing-LSTM approach, demonstrating the value of combining statistical and machine learning methods for large-scale forecasting.',
    'M5': 'M5 Competition (2020) focused on retail demand forecasting using Walmart sales data across 42,840 hierarchical time series. The winning solutions used gradient boosting (LightGBM) with extensive feature engineering, providing practical insights for supply chain forecasting.',
    'M6': 'M6 Competition (2022) combined time series forecasting with investment decision-making, requiring participants to both predict and act on financial instrument data. It bridged forecasting accuracy and decision quality in real financial settings.',
    'Kaggle TS': 'Kaggle TS refers to time series datasets and benchmarks drawn from Kaggle competitions. These datasets reflect diverse real-world forecasting challenges across retail, finance, energy, and transportation, with solutions representing state-of-the-art practical approaches.',
    'Chronos-Pre': "Chronos-Pre represents the pre-training configuration of Amazon's Chronos family of probabilistic foundation models. Chronos treats time series forecasting as language modeling, tokenizing values into discrete bins and training T5-based transformers on vast collections of real and synthetic data.",
    'Chronos-Eval1': 'Chronos-Eval1 is the first evaluation configuration of Chronos, testing zero-shot forecasting performance on held-out datasets not seen during pre-training. It assesses in-distribution generalization across diverse temporal patterns and frequencies.',
    'Chronos-Eval2': 'Chronos-Eval2 is the second evaluation phase of Chronos, focusing on out-of-distribution generalization. It tests how well Chronos transfers to domain-specific datasets with characteristics underrepresented in its pre-training corpus.',
    'ChronosBolt-Pre': 'ChronosBolt-Pre is the pre-training setup for ChronosBolt, an improved and faster variant of Chronos using a more efficient patched architecture. ChronosBolt delivers competitive forecasting accuracy with significantly reduced inference latency.',
    'ChronosBolt-Eval1': "ChronosBolt-Eval1 evaluates ChronosBolt's zero-shot forecasting on standard benchmark datasets. It measures the improved efficiency-accuracy trade-off of the patched architecture compared to the original Chronos design.",
    'ChronosBolt-Eval2': 'ChronosBolt-Eval2 tests ChronosBolt on out-of-distribution datasets, evaluating cross-domain transfer. Its lighter architecture enables faster evaluation cycles while maintaining strong generalization performance.',
    'ChronosX-Pre': 'ChronosX-Pre is the pre-training phase of ChronosX, the extended Chronos architecture incorporating additional context length and improved tokenization strategies. ChronosX targets longer-horizon forecasting and richer seasonal patterns.',
    'ChronosX-Eval1': 'ChronosX-Eval1 tests ChronosX zero-shot performance on benchmark forecasting datasets, evaluating the benefits of extended context and improved architecture over standard Chronos.',
    'ChronosX-Eval2': "ChronosX-Eval2 assesses ChronosX on out-of-distribution forecasting scenarios, examining how architectural improvements affect robustness to domain shift and unseen temporal dynamics.",
    'ChronosX-Synth': "ChronosX-Synth evaluates ChronosX specifically on synthetic time series benchmarks, testing the model's ability to generalize to controlled, programmatically-generated patterns that test specific forecasting capabilities such as trend, noise, and seasonality.",
    'TSFM-Granite': "TSFM-Granite is IBM's Granite time series foundation model, part of the IBM TSFM (Time Series Foundation Model) family. Pre-trained on diverse time series corpora, Granite focuses on enterprise forecasting with strong out-of-the-box performance and fine-tuning efficiency for domain-specific applications.",
    'TSFM-Core': "TSFM-Core is the core architecture of IBM's time series foundation model framework. It provides the base pre-trained backbone upon which specialized variants like Granite are built, offering general-purpose time series representations.",
    'TSFM-Bench': "TSFM-Bench is the benchmarking suite for IBM's TSFM family, providing standardized evaluation protocols and datasets for comparing different foundation model variants and fine-tuning strategies.",
    'LOTSA': 'LOTSA (Large-scale Open Time Series Archive) is a large-scale dataset collection and evaluation framework for pre-training time series foundation models. It aggregates over a billion time series observations from public sources to enable data-driven pre-training at scale.',
    'TimesFM': "TimesFM (Time Series Foundation Model) is Google's pre-trained model for time series forecasting. It employs a patched-decoder architecture trained on a large corpus of Google-internal and public time series data. TimesFM provides strong zero-shot forecasting with competitive performance across multiple granularities.",
    'Timer-XL': 'Timer-XL is a large-scale time series foundation model from Tsinghua University designed for cross-domain forecasting. It uses generative pre-training with an auto-regressive transformer, supporting variable-length input and output horizons for flexible deployment.',
    'Time-MOE': 'Time-MOE (Time Series Mixture of Experts) uses a sparse mixture-of-experts transformer architecture for efficient time series forecasting at scale. It activates only a subset of parameters per input, achieving high accuracy with lower inference cost than dense models.',
    'TTM-PreT': "TTM-PreT (Tiny Time Mixer Pre-Training) represents the pre-training phase of IBM Research's TTM model. Tiny Time Mixer uses a lightweight MLP-mixer architecture pre-trained on diverse time series, enabling strong zero-shot and few-shot performance with minimal computational requirements.",
    'TTM-Eval': "TTM-Eval assesses Tiny Time Mixer's zero-shot forecasting quality on downstream benchmark datasets. It validates the transfer learning capability of the compact pre-trained model across different domains and time series characteristics.",
    'TTM-Bench': 'TTM-Bench is the full benchmarking evaluation of Tiny Time Mixer, comparing its pre-trained and fine-tuned variants against other foundation models and task-specific baselines.',
    'LPTM-Pre': 'LPTM-Pre (Large Pre-trained Time series Model Pre-Training) documents the pre-training strategy for LPTM, a foundation model trained on multi-domain time series corpora. It studies the effect of pre-training data composition, tokenization, and scale on downstream task performance.',
    'LPTM-Eval': 'LPTM-Eval is the evaluation benchmark for the LPTM foundation model, testing its performance across forecasting, classification, and anomaly detection tasks. It enables fair comparison between different pre-training strategies and model architectures.',
    'Tempo': 'Tempo (Temporal Pre-training using Masked Observation) is a self-supervised pre-training framework for time series using masked reconstruction. It learns robust temporal representations by reconstructing randomly masked portions of the input sequence, similar to BERT-style pre-training in NLP.',
    'InstructTime': 'InstructTime is an instruction-tuning framework for time series foundation models. Drawing from instruction-following paradigms in NLP, it fine-tunes pre-trained models using natural language task descriptions, enabling multi-task time series analysis through a single model.',
    'TimeBench': 'TimeBench is a comprehensive benchmarking framework for evaluating time series foundation models across a broad suite of tasks and datasets. It standardizes evaluation protocols for comparing zero-shot, few-shot, and fine-tuned model variants.',
    'TS2Vec-Bench': 'TS2Vec-Bench is an evaluation benchmark for time series contrastive representation learning methods. TS2Vec (Time Series to Vector) learns hierarchical contextual representations through temporal and instance contrastive objectives, and this benchmark evaluates those representations on downstream classification and anomaly detection tasks.',
    'TS2Vec-PreT': 'TS2Vec-PreT represents the pre-training phase of TS2Vec, where universal time series representations are learned without task-specific labels through multi-scale contrastive learning on unlabeled time series data.',
    'TSB-UAD MOMENT': 'TSB-UAD MOMENT is an anomaly detection benchmark using the MOMENT foundation model evaluated on the TSB-UAD (Time Series Benchmark for Unsupervised Anomaly Detection) suite. It tests zero-shot anomaly detection capability across diverse datasets including server metrics, ECG signals, and industrial sensor data.',
    'TSB-UAD Full': 'TSB-UAD Full is the complete Time Series Benchmark for Unsupervised Anomaly Detection suite, covering over 1,000 time series with ground-truth anomaly labels across multiple domains. It provides the most comprehensive evaluation of unsupervised anomaly detection methods available.',
    'Time-LLM': 'Time-LLM reprograms pre-trained large language models (LLMs) for time series forecasting. It converts time series into text-compatible representations and aligns temporal patterns with LLM token embeddings, enabling zero-shot and few-shot forecasting using models like LLaMA and GPT-2.',
    'AutoTimes': 'AutoTimes is an LLM-based time series forecasting framework that autoregressively generates future values using a pre-trained language model backbone. It augments time series tokens with temporal metadata and chain-of-thought prompting to improve multi-step forecasting quality.',
    'ST-LLM': 'ST-LLM (Spatio-Temporal LLM) adapts large language models for spatio-temporal forecasting tasks. It handles the joint modeling of spatial relationships and temporal dynamics, making it applicable to traffic forecasting, weather prediction, and other geographically structured time series.',
    'LLM-Time': 'LLM-Time evaluates general-purpose LLMs (GPT-3, GPT-4, LLaMA) on time series forecasting without any fine-tuning. It studies the emergent zero-shot forecasting capability of language models and reveals their strengths and limitations on numerical prediction tasks.',
    'LLM-Mixer': 'LLM-Mixer integrates LLM-based encoders with MLP-Mixer architectures for time series forecasting. It uses language model representations as rich feature encoders and combines them with efficient mixing layers for final prediction.',
    'LLM-prompt': 'LLM-prompt evaluates prompt engineering strategies for eliciting better time series forecasts from LLMs. It studies how different prompting formats — raw numbers, textual descriptions, chain-of-thought — affect forecasting accuracy on standard benchmarks.',
    'LLM-PS': "LLM-PS (LLM for Pattern and Semantics) combines LLMs' semantic understanding with pattern recognition for time series forecasting. It bridges textual context (domain knowledge, variable descriptions) with numerical temporal patterns for improved predictions.",
    'One Fits All': 'One Fits All (GPT4TS) demonstrates that a single pre-trained GPT-2 model can be fine-tuned with minimal adaptation to achieve state-of-the-art performance across diverse time series tasks including forecasting, classification, imputation, and anomaly detection.',
    'Lag-Llama': 'Lag-Llama is a probabilistic foundation model for time series forecasting built on the LLaMA transformer architecture. Pre-trained on a large corpus of diverse time series, it generates probabilistic forecasts and excels at zero-shot and few-shot generalization to unseen datasets.',
    'GHPT': 'GHPT (Generative Hybrid Pre-trained Transformer) is a hybrid time series model combining generative pre-training with task-specific fine-tuning. It learns general temporal patterns from large corpora and adapts efficiently to downstream forecasting and classification tasks.',
    'Automixer': 'Automixer is an automated mixing architecture for multivariate time series forecasting. It combines cross-variate and temporal mixing in a configurable MLP-based design and uses neural architecture search principles to find optimal mixing strategies for different datasets.',
    'TSMamba-ZS': "TSMamba-ZS (Zero-Shot) evaluates TSMamba — a state space model (SSM) based on Mamba architecture — in a zero-shot setting. Mamba's selective state space mechanism efficiently handles long-range dependencies in time series without the quadratic cost of transformers.",
    'TSMamba-FullShot': 'TSMamba-FullShot evaluates TSMamba with full fine-tuning on each target dataset. It assesses the upper bound performance of Mamba-based state space models when given complete access to downstream training data.',
    'DataLoop': 'DataLoop is a data management and MLOps platform that provides time series dataset curation, versioning, and annotation tools. In the context of this catalog, it represents datasets and benchmarks managed through the DataLoop ecosystem for structured model evaluation.',
    'FastML': 'FastML is a rapid prototyping framework for machine learning on time series data. It provides efficient implementations of common algorithms optimized for fast experimentation cycles, enabling quick baseline comparisons before committing to more computationally intensive approaches.',
    'Hackernoon': 'Hackernoon refers to time series benchmarks and datasets referenced in Hackernoon technical articles documenting applied machine learning experiments. These datasets are drawn from real-world use cases discussed in the developer community.',
    'TimeGPT': "TimeGPT is Nixtla's proprietary time series foundation model available via API. Pre-trained on over 100 billion data points, it delivers zero-shot forecasting across diverse domains with no fine-tuning required, making it one of the first commercially deployed time series foundation models.",
    'LightGTS': 'LightGTS (Lightweight Graph Time Series) is an efficient graph-based model for multivariate time series forecasting. It constructs dynamic inter-variable dependency graphs and applies lightweight graph convolutions to exploit spatial structure without the overhead of full graph neural networks.',
    'CiK': 'CiK (Covariates in Kindred) is a framework that systematically evaluates the effect of covariates and auxiliary variables on time series forecasting performance. It assesses how different models leverage additional context information to improve predictions.',
    'NSF HDR': 'NSF HDR refers to datasets and benchmarks associated with the NSF Harnessing the Data Revolution (HDR) program. These scientific time series come from NSF-funded research spanning astrophysics, geoscience, and other data-intensive disciplines.',
    'MLCommons-EQ': 'MLCommons-EQ (Earthquake) is a seismology benchmark from the MLCommons initiative focused on earthquake prediction and classification. It provides standardized training and evaluation protocols for machine learning models applied to seismic time series data.',
    'TS-RAGZSEval': 'TS-RAGZSEval evaluates Retrieval-Augmented Generation (RAG) approaches for time series forecasting in a zero-shot setting. RAG for time series retrieves similar historical patterns from a database to condition forecasts, reducing the need for domain-specific pre-training.',
    'TS-RAGPreT': 'TS-RAGPreT is the pre-training evaluation framework for RAG-enhanced time series models. It assesses how retrieval-augmented pre-training — combining pattern libraries with neural forecasters — improves generalization compared to standard pre-training approaches.',
    'Informer': 'Informer is an efficient transformer model designed for long sequence time series forecasting (LSTF). It introduces ProbSparse self-attention and self-attention distilling to reduce complexity from O(L²) to O(L log L). Originally benchmarked on electricity transformer temperature (ETT) datasets, it was a landmark paper demonstrating transformers for time series.',
    'TimesNet': '2D time series model that transforms 1D series into 2D tensors to simultaneously capture intra-period and inter-period variations using inception blocks. Achieves state-of-the-art results across forecasting, imputation, classification, and anomaly detection tasks.',
}

DEFAULT_DESCRIPTION = (
    "{name} is a time series model or benchmark evaluated across multiple "
    "datasets in the Time Series Commons catalog. It contributes to the "
    "systematic comparison of forecasting and analysis methods across diverse "
    "domains and temporal patterns."
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def count_datasets_for_model(all_datasets: list, model_name: str) -> int:
    return sum(
        1 for d in all_datasets
        if d.get("benchmarks", {}).get(model_name) is True
    )


# ---------------------------------------------------------------------------
# Core seeding functions
# ---------------------------------------------------------------------------

def seed_datasets(cur, all_datasets: list) -> int:
    upsert_sql = """
        INSERT INTO datasets (name, domain, source_url, metadata, updated_at)
        VALUES (%(name)s, %(domain)s, %(source_url)s, %(metadata)s, NOW())
        ON CONFLICT (name) DO UPDATE
            SET domain     = EXCLUDED.domain,
                source_url = EXCLUDED.source_url,
                metadata   = EXCLUDED.metadata,
                updated_at = NOW()
    """
    rows = []
    for item in all_datasets:
        metadata = {
            "slug":        item.get("id", ""),
            "timePoints":  item.get("timePoints", "Not specified"),
            "interval":    item.get("interval", "Not specified"),
            "variables":   item.get("variables", "Not specified"),
            "dimensions":  item.get("dimensions", "Not specified"),
            "description": item.get("description", ""),
            "paperLink":   item.get("paperLink", ""),
            "benchmarks":  item.get("benchmarks", {}),
        }
        rows.append({
            "name":       item["name"],
            "domain":     item.get("domain") or "General",
            "source_url": item.get("dataLink") or None,
            "metadata":   Json(metadata),
        })

    execute_batch(cur, upsert_sql, rows, page_size=200)
    return len(rows)


def seed_models(cur, all_datasets: list) -> int:
    upsert_sql = """
        INSERT INTO models (name, architecture, source_url, metadata, updated_at)
        VALUES (%(name)s, %(architecture)s, %(source_url)s, %(metadata)s, NOW())
        ON CONFLICT (name) DO UPDATE
            SET architecture = EXCLUDED.architecture,
                source_url   = EXCLUDED.source_url,
                metadata     = EXCLUDED.metadata,
                updated_at   = NOW()
    """
    rows = []
    for model_name in ALL_MODELS:
        datasets_count = count_datasets_for_model(all_datasets, model_name)
        description = MODEL_DESCRIPTIONS.get(
            model_name,
            DEFAULT_DESCRIPTION.format(name=model_name)
        )
        metadata = {
            "description":   description,
            "datasetsCount": datasets_count,
        }
        rows.append({
            "name":         model_name,
            "architecture": MODEL_ARCHITECTURES.get(model_name, "Library/Benchmark"),
            "source_url":   None,
            "metadata":     Json(metadata),
        })

    execute_batch(cur, upsert_sql, rows, page_size=100)
    return len(rows)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    db_conn_str = os.environ.get("DB_CONN_STR")
    if not db_conn_str:
        log.error("DB_CONN_STR environment variable is not set.")
        log.error("Example: DB_CONN_STR=postgresql://ts_user:PASSWORD@127.0.0.1:5432/timeseries_db")
        sys.exit(1)

    if not MODELS_JSON.exists():
        log.error(f"data/models.json not found at expected path: {MODELS_JSON}")
        sys.exit(1)

    log.info(f"Reading {MODELS_JSON} ...")
    with open(MODELS_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    all_datasets = data.get("models", [])
    log.info(f"Loaded {len(all_datasets)} dataset entries from JSON.")

    log.info("Connecting to PostgreSQL ...")
    try:
        conn = psycopg2.connect(db_conn_str)
    except psycopg2.OperationalError as e:
        log.error(f"Failed to connect: {e}")
        sys.exit(1)

    try:
        with conn:
            with conn.cursor() as cur:
                log.info("Seeding datasets table ...")
                n_datasets = seed_datasets(cur, all_datasets)
                log.info(f"  Upserted {n_datasets} datasets.")

                log.info("Seeding models table ...")
                n_models = seed_models(cur, all_datasets)
                log.info(f"  Upserted {n_models} models.")

        log.info("Seed complete. Summary:")
        log.info(f"  datasets rows upserted : {n_datasets}")
        log.info(f"  models   rows upserted : {n_models}")
    except Exception as e:
        log.error(f"Seed failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
