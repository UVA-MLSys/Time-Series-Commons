/**
 * Time Series Commons - NotebookLM-Style Interface
 * Models and Datasets Catalog
 */

const DOMAIN_ICONS = {
    'Energy': `<svg viewBox="0 0 24 24"><polyline points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>`,
    'Health': `<svg viewBox="0 0 24 24"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>`,
    'Nature': `<svg viewBox="0 0 24 24"><path d="M17 8C8 10 5.9 16.17 3.82 21.34L5.71 22l1-2.3A4.49 4.49 0 0 0 8 20C19 20 22 3 22 3c-1 2-8 2-8 2"/><path d="M3.82 21.34A15 15 0 0 1 8 16.5c4-1 6-4 6-4"/></svg>`,
    'Economics': `<svg viewBox="0 0 24 24"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>`,
    'Transportation': `<svg viewBox="0 0 24 24"><rect x="1" y="3" width="15" height="13" rx="2"/><path d="M16 8h4l3 5v3h-7V8z"/><circle cx="5.5" cy="18.5" r="2.5"/><circle cx="18.5" cy="18.5" r="2.5"/></svg>`,
    'Industry': `<svg viewBox="0 0 24 24"><path d="M2 20a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V8l-7-6H4a2 2 0 0 0-2 2v16z"/><path d="M9 22V12h6v10"/><path d="M14 2v6h6"/><circle cx="12" cy="7" r="1"/></svg>`,
    'Motion': `<svg viewBox="0 0 24 24"><circle cx="12" cy="5" r="1"/><path d="M20 9a2 2 0 0 0-2-2h-2.5l-1.45-1.45A2 2 0 0 0 12.6 5H11.4a2 2 0 0 0-1.45.55L8.5 7H6a2 2 0 0 0-2 2v4a2 2 0 0 0 2 2h.93l1.03 4H9l.5-2h5l.5 2h1.04l1.03-4H18a2 2 0 0 0 2-2V9z"/></svg>`,
    'Corporate': `<svg viewBox="0 0 24 24"><rect x="2" y="7" width="20" height="14" rx="2" ry="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/></svg>`,
    'Retail': `<svg viewBox="0 0 24 24"><path d="M6 2L3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"/><line x1="3" y1="6" x2="21" y2="6"/><path d="M16 10a4 4 0 0 1-8 0"/></svg>`,
    'Sensor': `<svg viewBox="0 0 24 24"><path d="M5 12.55a11 11 0 0 1 14.08 0"/><path d="M1.42 9a16 16 0 0 1 21.16 0"/><path d="M8.53 16.11a6 6 0 0 1 6.95 0"/><circle cx="12" cy="20" r="1" fill="currentColor"/></svg>`,
    'Demographics': `<svg viewBox="0 0 24 24"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>`,
    'Audio': `<svg viewBox="0 0 24 24"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/></svg>`,
    'Image': `<svg viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>`,
    'Synthetic': `<svg viewBox="0 0 24 24"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>`,
};

class NotebookCatalog {
    constructor() {
        this.allData = [];
        this.datasets = [];
        this.models = [];
        this.domainConfig = null;
        this.currentTab = 'all';
        this.currentView = 'grid'; // Default to grid for featured sections
        this.currentSort = 'name';
        this.searchQuery = '';
        this.activeDomain = null; // Domain filter set by explorer tiles
        
        this.init();
    }

    async init() {
        try {
            await this.loadData();
            await this.loadDomainConfig();
            this.processData();
            this.setupEventListeners();
            this.renderContent();
        } catch (error) {
            console.error('Error initializing catalog:', error);
            this.showError();
        }
    }

    async loadData() {
        const response = await fetch('./data/models.json');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        this.allData = data.models || [];
    }

    async loadDomainConfig() {
        try {
            const response = await fetch('./data/domain-config.json');
            if (!response.ok) {
                console.warn('Could not load domain config, using defaults');
                return;
            }
            this.domainConfig = await response.json();
        } catch (error) {
            console.warn('Error loading domain config:', error);
        }
    }

    getDomainConfig(domainName) {
        if (!this.domainConfig || !domainName) {
            return { image: '', color: '#95a5a6', category: 'Sensor' };
        }

        const domainLower = domainName.toLowerCase();
        
        // Try exact match first (case-insensitive)
        for (const [category, config] of Object.entries(this.domainConfig.domains)) {
            if (category.toLowerCase() === domainLower) {
                return { ...config, category };
            }
        }
        
        // Try keyword matching
        let bestMatch = null;
        let maxMatchCount = 0;
        
        for (const [category, config] of Object.entries(this.domainConfig.domains)) {
            let matchCount = 0;
            for (const keyword of config.keywords) {
                if (domainLower.includes(keyword.toLowerCase())) {
                    matchCount++;
                }
            }
            
            // Keep track of best match
            if (matchCount > maxMatchCount) {
                maxMatchCount = matchCount;
                bestMatch = { ...config, category };
            }
        }
        
        // Return best match or default to Sensor
        if (bestMatch) {
            return bestMatch;
        }
        
        // Fallback to Sensor category
        return {
            image: 'pics/domains/sensor.jpg',
            color: '#3498db',
            category: 'Sensor'
        };
    }

    processData() {
        // Separate datasets and extract unique models
        this.datasets = this.allData;

        // Complete list of all 79 models from the CSV benchmark columns
        const ALL_MODELS = [
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
            'LightGTS', 'CiK', 'NSF HDR', 'MLCommons-EQ'
        ];

        // Domain map: each model assigned to its most relevant domain category
        const modelDomainMap = {
            // Energy-focused models (ETT, electricity benchmarks)
            'Informer': 'Energy',
            'Autoformer': 'Energy',
            'FEDformer': 'Energy',
            'TimesNet': 'Energy',
            'TSLib': 'Energy',
            'TSFM-Core': 'Energy',
            'TSFM-Bench': 'Energy',
            'TSFM-Granite': 'Energy',
            // Foundation/pre-trained models (multi-domain synthetic pre-training)
            'Chronos-Pre': 'Synthetic',
            'Chronos-Eval1': 'Synthetic',
            'Chronos-Eval2': 'Synthetic',
            'ChronosBolt-Pre': 'Synthetic',
            'ChronosBolt-Eval1': 'Synthetic',
            'ChronosBolt-Eval2': 'Synthetic',
            'ChronosX-Pre': 'Synthetic',
            'ChronosX-Eval1': 'Synthetic',
            'ChronosX-Eval2': 'Synthetic',
            'ChronosX-Synth': 'Synthetic',
            'TimesFM': 'Synthetic',
            'Time-MOE': 'Synthetic',
            'Timer-XL': 'Synthetic',
            'LPTM-Pre': 'Synthetic',
            'LPTM-Eval': 'Synthetic',
            'TS2Vec-Bench': 'Synthetic',
            'TS2Vec-PreT': 'Synthetic',
            'Automixer': 'Synthetic',
            'TTM-PreT': 'Synthetic',
            'TTM-Eval': 'Synthetic',
            'TTM-Bench': 'Synthetic',
            'TSMamba-ZS': 'Synthetic',
            'TSMamba-FullShot': 'Synthetic',
            'UTSD': 'Synthetic',
            'DataLoop': 'Synthetic',
            'LOTSA': 'Synthetic',
            'InstructTime': 'Synthetic',
            'Tempo': 'Synthetic',
            'TimeBench': 'Synthetic',
            'MONSTER': 'Synthetic',
            // Business/economics forecasting
            'Prophet': 'Economics',
            'TimeGPT': 'Economics',
            'AutoGluon': 'Economics',
            'NeuralForecast': 'Economics',
            'M1': 'Economics',
            'M2': 'Economics',
            'M3': 'Economics',
            'M4': 'Economics',
            'M5': 'Retail',
            'M6': 'Economics',
            'Monash': 'Economics',
            'Monash-Common': 'Economics',
            'Monash-small': 'Economics',
            'Monash TSER': 'Economics',
            'Monash Moment': 'Economics',
            'Kaggle TS': 'Economics',
            'FastML': 'Economics',
            'Hackernoon': 'Corporate',
            // Time series classification archives
            'UCR': 'Motion',
            'UEA': 'Motion',
            'NonUCR-UCI': 'Motion',
            'Aeon': 'Motion',
            // Anomaly detection
            'TSB-UAD MOMENT': 'Industry',
            'TSB-UAD Full': 'Industry',
            'Merlion': 'Industry',
            // LLM-based models
            'Time-LLM': 'Corporate',
            'AutoTimes': 'Corporate',
            'ST-LLM': 'Corporate',
            'LLM-Time': 'Corporate',
            'LLM-Mixer': 'Corporate',
            'LLM-prompt': 'Corporate',
            'LLM-PS': 'Corporate',
            'One Fits All': 'Corporate',
            'Lag-Llama': 'Corporate',
            'GHPT': 'Corporate',
            // RAG / retrieval-based
            'TS-RAGZSEval': 'Synthetic',
            'TS-RAGPreT': 'Synthetic',
            // Specialized
            'LightGTS': 'Transportation',
            'CiK': 'Industry',
            'NSF HDR': 'Nature',
            'MLCommons-EQ': 'Nature',
        };

        // Build model list from all known CSV columns
        this.models = ALL_MODELS.map(modelName => {
            const datasetsCount = this.allData.filter(d =>
                d.benchmarks && d.benchmarks[modelName]
            ).length;

            return {
                id: modelName.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, ''),
                name: modelName,
                type: 'model',
                datasetsCount: datasetsCount,
                domain: modelDomainMap[modelName] || 'Synthetic',
                description: this.getModelDescription(modelName)
            };
        });
    }

    getModelDescription(modelName) {
        const descriptions = {
            // --- Core Libraries ---
            'Darts': 'Darts (Data Analysis and Real-Time Systems) is a Python library for time series forecasting developed by Unit8. It offers a unified interface for multiple forecasting models including statistical methods (ARIMA, ETS), machine learning approaches (Random Forests, LightGBM), and deep learning models (N-BEATS, Transformer). Darts supports both univariate and multivariate forecasting, handles covariates, and provides probabilistic forecasting capabilities with confidence intervals.',
            'Merlion': 'Merlion is a Python library for time series intelligence developed by Salesforce Research. It provides a unified interface for time series forecasting, anomaly detection, and change point detection. Merlion includes implementations of state-of-the-art algorithms including ARIMA, Prophet, LSTM, Transformer models, and ensemble methods. It emphasizes production-ready deployment with automatic hyperparameter tuning and model selection.',
            'Aeon': 'Aeon (formerly sktime) is a scikit-learn compatible Python toolkit for time series analysis. It provides a comprehensive suite of algorithms for time series classification, regression, clustering, and annotation. Aeon includes distance-based methods, shapelet transforms, dictionary-based approaches, and deep learning models. It emphasizes composability and modularity, allowing users to build complex pipelines.',
            'TSLib': 'TSLib (Time Series Library) is a comprehensive toolkit providing implementations of state-of-the-art time series forecasting models. It includes classic methods, modern deep learning approaches, and recent transformer-based architectures. TSLib emphasizes reproducible research with standardized experimental protocols and is widely used for benchmarking new forecasting methods.',
            'AutoGluon': 'AutoGluon-TimeSeries is an AutoML toolkit that automatically trains and ensembles multiple forecasting models. Developed by Amazon, it simplifies time series forecasting by automating model selection, hyperparameter tuning, and ensemble construction. AutoGluon combines statistical models (ETS, ARIMA), tree-based methods (CatBoost, LightGBM), and deep learning approaches for best-in-class performance.',
            'NeuralForecast': 'NeuralForecast is Nixtla\'s deep learning library for time series forecasting. It provides scalable neural architectures (NHITS, NBEATS, TFT, DeepAR, Transformer) with a simple scikit-learn-style API. NeuralForecast supports probabilistic forecasting, automatic hyperparameter optimization, and efficient training on large datasets.',
            'Prophet': 'Prophet is Meta\'s open-source forecasting tool based on additive decomposition of trend, seasonality, and holiday effects. Designed for business time series with strong seasonal patterns, it handles missing data and outliers robustly and requires minimal manual tuning, making it widely adopted in industry.',
            // --- Archive Benchmarks ---
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
            // --- Competition Benchmarks ---
            'M1': 'M1 Competition (1982) was the first Makridakis forecasting competition, evaluating statistical and judgmental methods on 1,001 economic and business time series. Its findings challenged the dominance of complex models and established benchmarking standards for the field.',
            'M2': 'M2 Competition (1993) extended the M1 study with a focus on real-time updating and tracking signals. It evaluated 29 methods on monthly, quarterly, and yearly economic data, reinforcing insights about the value of simple statistical methods.',
            'M3': 'M3 Competition (2000) is the most widely cited forecasting competition, covering 3,003 time series across economic, industry, finance, and demographic domains. Its results strongly influenced practice and highlighted the robustness of simple benchmarks like Theta and exponential smoothing.',
            'M4': 'M4 Competition (2018) evaluated 60 methods on 100,000 time series from six frequencies. It was won by a hybrid Exponential Smoothing-LSTM approach, demonstrating the value of combining statistical and machine learning methods for large-scale forecasting.',
            'M5': 'M5 Competition (2020) focused on retail demand forecasting using Walmart sales data across 42,840 hierarchical time series. The winning solutions used gradient boosting (LightGBM) with extensive feature engineering, providing practical insights for supply chain forecasting.',
            'M6': 'M6 Competition (2022) combined time series forecasting with investment decision-making, requiring participants to both predict and act on financial instrument data. It bridged forecasting accuracy and decision quality in real financial settings.',
            'Kaggle TS': 'Kaggle TS refers to time series datasets and benchmarks drawn from Kaggle competitions. These datasets reflect diverse real-world forecasting challenges across retail, finance, energy, and transportation, with solutions representing state-of-the-art practical approaches.',
            // --- Foundation Models (Amazon Chronos Family) ---
            'Chronos-Pre': 'Chronos-Pre represents the pre-training configuration of Amazon\'s Chronos family of probabilistic foundation models. Chronos treats time series forecasting as language modeling, tokenizing values into discrete bins and training T5-based transformers on vast collections of real and synthetic data.',
            'Chronos-Eval1': 'Chronos-Eval1 is the first evaluation configuration of Chronos, testing zero-shot forecasting performance on held-out datasets not seen during pre-training. It assesses in-distribution generalization across diverse temporal patterns and frequencies.',
            'Chronos-Eval2': 'Chronos-Eval2 is the second evaluation phase of Chronos, focusing on out-of-distribution generalization. It tests how well Chronos transfers to domain-specific datasets with characteristics underrepresented in its pre-training corpus.',
            'ChronosBolt-Pre': 'ChronosBolt-Pre is the pre-training setup for ChronosBolt, an improved and faster variant of Chronos using a more efficient patched architecture. ChronosBolt delivers competitive forecasting accuracy with significantly reduced inference latency.',
            'ChronosBolt-Eval1': 'ChronosBolt-Eval1 evaluates ChronosBolt\'s zero-shot forecasting on standard benchmark datasets. It measures the improved efficiency-accuracy trade-off of the patched architecture compared to the original Chronos design.',
            'ChronosBolt-Eval2': 'ChronosBolt-Eval2 tests ChronosBolt on out-of-distribution datasets, evaluating cross-domain transfer. Its lighter architecture enables faster evaluation cycles while maintaining strong generalization performance.',
            'ChronosX-Pre': 'ChronosX-Pre is the pre-training phase of ChronosX, the extended Chronos architecture incorporating additional context length and improved tokenization strategies. ChronosX targets longer-horizon forecasting and richer seasonal patterns.',
            'ChronosX-Eval1': 'ChronosX-Eval1 tests ChronosX zero-shot performance on benchmark forecasting datasets, evaluating the benefits of extended context and improved architecture over standard Chronos.',
            'ChronosX-Eval2': 'ChronosX-Eval2 assesses ChronosX on out-of-distribution forecasting scenarios, examining how architectural improvements affect robustness to domain shift and unseen temporal dynamics.',
            'ChronosX-Synth': 'ChronosX-Synth evaluates ChronosX specifically on synthetic time series benchmarks, testing the model\'s ability to generalize to controlled, programmatically-generated patterns that test specific forecasting capabilities such as trend, noise, and seasonality.',
            // --- Foundation Models (IBM/HuggingFace) ---
            'TSFM-Granite': 'TSFM-Granite is IBM\'s Granite time series foundation model, part of the IBM TSFM (Time Series Foundation Model) family. Pre-trained on diverse time series corpora, Granite focuses on enterprise forecasting with strong out-of-the-box performance and fine-tuning efficiency for domain-specific applications.',
            'TSFM-Core': 'TSFM-Core is the core architecture of IBM\'s time series foundation model framework. It provides the base pre-trained backbone upon which specialized variants like Granite are built, offering general-purpose time series representations.',
            'TSFM-Bench': 'TSFM-Bench is the benchmarking suite for IBM\'s TSFM family, providing standardized evaluation protocols and datasets for comparing different foundation model variants and fine-tuning strategies.',
            // --- Foundation Models (Others) ---
            'LOTSA': 'LOTSA (Large-scale Open Time Series Archive) is a large-scale dataset collection and evaluation framework for pre-training time series foundation models. It aggregates over a billion time series observations from public sources to enable data-driven pre-training at scale.',
            'TimesFM': 'TimesFM (Time Series Foundation Model) is Google\'s pre-trained model for time series forecasting. It employs a patched-decoder architecture trained on a large corpus of Google-internal and public time series data. TimesFM provides strong zero-shot forecasting with competitive performance across multiple granularities.',
            'Timer-XL': 'Timer-XL is a large-scale time series foundation model from Tsinghua University designed for cross-domain forecasting. It uses generative pre-training with an auto-regressive transformer, supporting variable-length input and output horizons for flexible deployment.',
            'Time-MOE': 'Time-MOE (Time Series Mixture of Experts) uses a sparse mixture-of-experts transformer architecture for efficient time series forecasting at scale. It activates only a subset of parameters per input, achieving high accuracy with lower inference cost than dense models.',
            'TTM-PreT': 'TTM-PreT (Tiny Time Mixer Pre-Training) represents the pre-training phase of IBM Research\'s TTM model. Tiny Time Mixer uses a lightweight MLP-mixer architecture pre-trained on diverse time series, enabling strong zero-shot and few-shot performance with minimal computational requirements.',
            'TTM-Eval': 'TTM-Eval assesses Tiny Time Mixer\'s zero-shot forecasting quality on downstream benchmark datasets. It validates the transfer learning capability of the compact pre-trained model across different domains and time series characteristics.',
            'TTM-Bench': 'TTM-Bench is the full benchmarking evaluation of Tiny Time Mixer, comparing its pre-trained and fine-tuned variants against other foundation models and task-specific baselines.',
            'LPTM-Pre': 'LPTM-Pre (Large Pre-trained Time series Model Pre-Training) documents the pre-training strategy for LPTM, a foundation model trained on multi-domain time series corpora. It studies the effect of pre-training data composition, tokenization, and scale on downstream task performance.',
            'LPTM-Eval': 'LPTM-Eval is the evaluation benchmark for the LPTM foundation model, testing its performance across forecasting, classification, and anomaly detection tasks. It enables fair comparison between different pre-training strategies and model architectures.',
            'Tempo': 'Tempo (Temporal Pre-training using Masked Observation) is a self-supervised pre-training framework for time series using masked reconstruction. It learns robust temporal representations by reconstructing randomly masked portions of the input sequence, similar to BERT-style pre-training in NLP.',
            'InstructTime': 'InstructTime is an instruction-tuning framework for time series foundation models. Drawing from instruction-following paradigms in NLP, it fine-tunes pre-trained models using natural language task descriptions, enabling multi-task time series analysis through a single model.',
            'TimeBench': 'TimeBench is a comprehensive benchmarking framework for evaluating time series foundation models across a broad suite of tasks and datasets. It standardizes evaluation protocols for comparing zero-shot, few-shot, and fine-tuned model variants.',
            // --- Representation Learning ---
            'TS2Vec-Bench': 'TS2Vec-Bench is an evaluation benchmark for time series contrastive representation learning methods. TS2Vec (Time Series to Vector) learns hierarchical contextual representations through temporal and instance contrastive objectives, and this benchmark evaluates those representations on downstream classification and anomaly detection tasks.',
            'TS2Vec-PreT': 'TS2Vec-PreT represents the pre-training phase of TS2Vec, where universal time series representations are learned without task-specific labels through multi-scale contrastive learning on unlabeled time series data.',
            // --- Anomaly Detection ---
            'TSB-UAD MOMENT': 'TSB-UAD MOMENT is an anomaly detection benchmark using the MOMENT foundation model evaluated on the TSB-UAD (Time Series Benchmark for Unsupervised Anomaly Detection) suite. It tests zero-shot anomaly detection capability across diverse datasets including server metrics, ECG signals, and industrial sensor data.',
            'TSB-UAD Full': 'TSB-UAD Full is the complete Time Series Benchmark for Unsupervised Anomaly Detection suite, covering over 1,000 time series with ground-truth anomaly labels across multiple domains. It provides the most comprehensive evaluation of unsupervised anomaly detection methods available.',
            // --- LLM-Based Models ---
            'Time-LLM': 'Time-LLM reprograms pre-trained large language models (LLMs) for time series forecasting. It converts time series into text-compatible representations and aligns temporal patterns with LLM token embeddings, enabling zero-shot and few-shot forecasting using models like LLaMA and GPT-2.',
            'AutoTimes': 'AutoTimes is an LLM-based time series forecasting framework that autoregressively generates future values using a pre-trained language model backbone. It augments time series tokens with temporal metadata and chain-of-thought prompting to improve multi-step forecasting quality.',
            'ST-LLM': 'ST-LLM (Spatio-Temporal LLM) adapts large language models for spatio-temporal forecasting tasks. It handles the joint modeling of spatial relationships and temporal dynamics, making it applicable to traffic forecasting, weather prediction, and other geographically structured time series.',
            'LLM-Time': 'LLM-Time evaluates general-purpose LLMs (GPT-3, GPT-4, LLaMA) on time series forecasting without any fine-tuning. It studies the emergent zero-shot forecasting capability of language models and reveals their strengths and limitations on numerical prediction tasks.',
            'LLM-Mixer': 'LLM-Mixer integrates LLM-based encoders with MLP-Mixer architectures for time series forecasting. It uses language model representations as rich feature encoders and combines them with efficient mixing layers for final prediction.',
            'LLM-prompt': 'LLM-prompt evaluates prompt engineering strategies for eliciting better time series forecasts from LLMs. It studies how different prompting formats — raw numbers, textual descriptions, chain-of-thought — affect forecasting accuracy on standard benchmarks.',
            'LLM-PS': 'LLM-PS (LLM for Pattern and Semantics) combines LLMs\' semantic understanding with pattern recognition for time series forecasting. It bridges textual context (domain knowledge, variable descriptions) with numerical temporal patterns for improved predictions.',
            'One Fits All': 'One Fits All (GPT4TS) demonstrates that a single pre-trained GPT-2 model can be fine-tuned with minimal adaptation to achieve state-of-the-art performance across diverse time series tasks including forecasting, classification, imputation, and anomaly detection.',
            'Lag-Llama': 'Lag-Llama is a probabilistic foundation model for time series forecasting built on the LLaMA transformer architecture. Pre-trained on a large corpus of diverse time series, it generates probabilistic forecasts and excels at zero-shot and few-shot generalization to unseen datasets.',
            'GHPT': 'GHPT (Generative Hybrid Pre-trained Transformer) is a hybrid time series model combining generative pre-training with task-specific fine-tuning. It learns general temporal patterns from large corpora and adapts efficiently to downstream forecasting and classification tasks.',
            // --- MLP/Linear Models ---
            'Automixer': 'Automixer is an automated mixing architecture for multivariate time series forecasting. It combines cross-variate and temporal mixing in a configurable MLP-based design and uses neural architecture search principles to find optimal mixing strategies for different datasets.',
            // --- TSMamba (State Space Models) ---
            'TSMamba-ZS': 'TSMamba-ZS (Zero-Shot) evaluates TSMamba — a state space model (SSM) based on Mamba architecture — in a zero-shot setting. Mamba\'s selective state space mechanism efficiently handles long-range dependencies in time series without the quadratic cost of transformers.',
            'TSMamba-FullShot': 'TSMamba-FullShot evaluates TSMamba with full fine-tuning on each target dataset. It assesses the upper bound performance of Mamba-based state space models when given complete access to downstream training data.',
            // --- Other Frameworks ---
            'DataLoop': 'DataLoop is a data management and MLOps platform that provides time series dataset curation, versioning, and annotation tools. In the context of this catalog, it represents datasets and benchmarks managed through the DataLoop ecosystem for structured model evaluation.',
            'FastML': 'FastML is a rapid prototyping framework for machine learning on time series data. It provides efficient implementations of common algorithms optimized for fast experimentation cycles, enabling quick baseline comparisons before committing to more computationally intensive approaches.',
            'Hackernoon': 'Hackernoon refers to time series benchmarks and datasets referenced in Hackernoon technical articles documenting applied machine learning experiments. These datasets are drawn from real-world use cases discussed in the developer community.',
            'TimeGPT': 'TimeGPT is Nixtla\'s proprietary time series foundation model available via API. Pre-trained on over 100 billion data points, it delivers zero-shot forecasting across diverse domains with no fine-tuning required, making it one of the first commercially deployed time series foundation models.',
            'LightGTS': 'LightGTS (Lightweight Graph Time Series) is an efficient graph-based model for multivariate time series forecasting. It constructs dynamic inter-variable dependency graphs and applies lightweight graph convolutions to exploit spatial structure without the overhead of full graph neural networks.',
            'CiK': 'CiK (Covariates in Kindred) is a framework that systematically evaluates the effect of covariates and auxiliary variables on time series forecasting performance. It assesses how different models leverage additional context information to improve predictions.',
            'NSF HDR': 'NSF HDR refers to datasets and benchmarks associated with the NSF Harnessing the Data Revolution (HDR) program. These scientific time series come from NSF-funded research spanning astrophysics, geoscience, and other data-intensive disciplines.',
            'MLCommons-EQ': 'MLCommons-EQ (Earthquake) is a seismology benchmark from the MLCommons initiative focused on earthquake prediction and classification. It provides standardized training and evaluation protocols for machine learning models applied to seismic time series data.',
            // --- RAG / Retrieval ---
            'TS-RAGZSEval': 'TS-RAGZSEval evaluates Retrieval-Augmented Generation (RAG) approaches for time series forecasting in a zero-shot setting. RAG for time series retrieves similar historical patterns from a database to condition forecasts, reducing the need for domain-specific pre-training.',
            'TS-RAGPreT': 'TS-RAGPreT is the pre-training evaluation framework for RAG-enhanced time series models. It assesses how retrieval-augmented pre-training — combining pattern libraries with neural forecasters — improves generalization compared to standard pre-training approaches.',
            // --- Classic Transformer-based ---
            'Informer': 'Informer is an efficient transformer model designed for long sequence time series forecasting (LSTF). It introduces ProbSparse self-attention and self-attention distilling to reduce complexity from O(L²) to O(L log L). Originally benchmarked on electricity transformer temperature (ETT) datasets, it was a landmark paper demonstrating transformers for time series.',
            'TimesNet': 'TimesNet transforms 1D time series into 2D tensors to simultaneously capture intra-period and inter-period variations. It applies 2D convolutions (inception blocks) to this multi-period representation, achieving state-of-the-art results across forecasting, imputation, classification, and anomaly detection tasks.',
            'TimesFM': 'TimesFM (Time Series Foundation Model) is Google\'s pre-trained model for time series forecasting. It employs a patched-decoder architecture trained on a large corpus of real-world and synthetic time series. TimesFM provides zero-shot forecasting capabilities and demonstrates strong performance across various forecasting horizons.'
        };

        return descriptions[modelName] || `${modelName} is a time series model or benchmark evaluated across multiple datasets in the Time Series Commons catalog. It contributes to the systematic comparison of forecasting and analysis methods across diverse domains and temporal patterns.`;
    }

    setupEventListeners() {
        // Tab navigation
        document.querySelectorAll('.nav-tab').forEach(tab => {
            tab.addEventListener('click', (e) => {
                const tabName = e.target.dataset.tab;
                this.switchTab(tabName);
            });
        });

        // Search
        const searchInput = document.getElementById('search-input');
        searchInput.addEventListener('input', (e) => {
            this.searchQuery = e.target.value.toLowerCase();
            this.renderContent();
        });

        // View toggle
        document.querySelectorAll('.view-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const view = e.currentTarget.dataset.view;
                this.switchView(view);
            });
        });

        // Sort dropdown
        document.getElementById('sort-select').addEventListener('change', (e) => {
            this.currentSort = e.target.value;
            this.renderContent();
        });

        // See all buttons
        document.querySelectorAll('.see-all-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const section = e.currentTarget.dataset.section;
                this.switchTab(section);
            });
        });

        // Modal close button
        const modalOverlay = document.getElementById('modal-overlay');
        const modalClose = document.getElementById('modal-close');
        
        if (modalClose) {
            modalClose.addEventListener('click', () => this.closeModal());
        }
        
        if (modalOverlay) {
            modalOverlay.addEventListener('click', (e) => {
                if (e.target === modalOverlay) {
                    this.closeModal();
                }
            });
        }
    }

    switchTab(tabName) {
        this.currentTab = tabName;
        
        // Update tab buttons
        document.querySelectorAll('.nav-tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.tab === tabName);
        });

        // Update views
        document.getElementById('all-view').classList.toggle('hidden', tabName !== 'all');
        document.getElementById('datasets-view').classList.toggle('hidden', tabName !== 'datasets');
        document.getElementById('models-view').classList.toggle('hidden', tabName !== 'models');

        // Set default view: list for datasets/models tabs, grid for 'all' tab (featured sections)
        if (tabName === 'datasets' || tabName === 'models') {
            this.switchView('list');
        } else if (tabName === 'all') {
            // Featured sections default to grid view
            this.switchView('grid');
        }

        this.renderContent();
    }

    switchView(view) {
        this.currentView = view;
        
        // Update view buttons
        document.querySelectorAll('.view-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.view === view);
        });

        this.renderContent();
    }

    renderContent() {
        if (this.currentTab === 'all') {
            this.renderFeatured();
            this.renderDomainExplorer();
        } else if (this.currentTab === 'datasets') {
            this.renderAllDatasets();
        } else if (this.currentTab === 'models') {
            this.renderAllModels();
        }
    }

    renderFeatured() {
        // Render featured datasets (first 4)
        const featuredDatasets = this.getFilteredAndSorted(this.datasets).slice(0, 4);
        const featuredDatasetsGrid = document.getElementById('featured-datasets-grid');
        const featuredDatasetsList = document.getElementById('featured-datasets-list');
        
        if (this.currentView === 'grid') {
            this.renderCards(featuredDatasets, 'featured-datasets-grid', 'dataset');
            if (featuredDatasetsGrid) featuredDatasetsGrid.classList.remove('hidden');
            if (featuredDatasetsList) featuredDatasetsList.classList.remove('active');
        } else {
            this.renderList(featuredDatasets, 'featured-datasets-list', 'dataset');
            if (featuredDatasetsGrid) featuredDatasetsGrid.classList.add('hidden');
            if (featuredDatasetsList) featuredDatasetsList.classList.add('active');
        }

        // Render featured models (first 4)
        const featuredModels = this.getFilteredAndSorted(this.models).slice(0, 4);
        const featuredModelsGrid = document.getElementById('featured-models-grid');
        const featuredModelsList = document.getElementById('featured-models-list');
        
        if (this.currentView === 'grid') {
            this.renderCards(featuredModels, 'featured-models-grid', 'model');
            if (featuredModelsGrid) featuredModelsGrid.classList.remove('hidden');
            if (featuredModelsList) featuredModelsList.classList.remove('active');
        } else {
            this.renderList(featuredModels, 'featured-models-list', 'model');
            if (featuredModelsGrid) featuredModelsGrid.classList.add('hidden');
            if (featuredModelsList) featuredModelsList.classList.add('active');
        }
    }

    renderDomainExplorer() {
        const grid = document.getElementById('domain-explorer-grid');
        if (!grid || !this.domainConfig) return;

        // Count datasets per domain category
        const domainCounts = {};
        this.datasets.forEach(d => {
            const cat = this.getDomainConfig(d.domain).category;
            domainCounts[cat] = (domainCounts[cat] || 0) + 1;
        });

        // Bento layout: assign grid spans to create visual rhythm across 7 cols / 2 rows
        // Wider tiles for high-count domains
        const BENTO_SPANS = {
            'Energy':         { col: 2, row: 1 },
            'Health':         { col: 2, row: 1 },
            'Nature':         { col: 1, row: 1 },
            'Economics':      { col: 2, row: 1 },
            'Transportation': { col: 1, row: 1 },  // row 1 done (7 cols)
            'Industry':       { col: 2, row: 1 },
            'Motion':         { col: 1, row: 1 },
            'Corporate':      { col: 2, row: 1 },
            'Retail':         { col: 1, row: 1 },  // row 2 done (7 cols)
            'Sensor':         { col: 1, row: 1 },
            'Demographics':   { col: 1, row: 1 },
            'Audio':          { col: 1, row: 1 },
            'Image':          { col: 1, row: 1 },
            'Synthetic':      { col: 1, row: 1 },
        };

        const entries = Object.entries(this.domainConfig.domains);
        grid.innerHTML = entries.map(([name, config]) => {
            const count = domainCounts[name] || 0;
            const icon = DOMAIN_ICONS[name] || '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/></svg>';
            const span = BENTO_SPANS[name] || { col: 1, row: 1 };
            const spanStyle = span.col > 1 ? `grid-column: span ${span.col};` : '';
            const isActive = this.activeDomain === name;
            const activeClass = isActive ? ' domain-tile--active' : '';
            return `
                <div class="domain-tile${activeClass}" data-domain="${name}"
                     style="${spanStyle} background-image: url('${config.image}'); --tile-color: ${config.color};">
                    <div class="domain-tile-overlay"></div>
                    <div class="domain-tile-content">
                        <div class="domain-tile-icon">${icon}</div>
                        <div class="domain-tile-name">${name}</div>
                        <div class="domain-tile-count">${count} dataset${count !== 1 ? 's' : ''}</div>
                    </div>
                </div>
            `;
        }).join('');

        grid.querySelectorAll('.domain-tile').forEach(tile => {
            tile.addEventListener('click', () => {
                this.activeDomain = tile.dataset.domain;
                this.switchTab('datasets');
            });
        });
    }

    clearDomainFilter() {
        this.activeDomain = null;
        this.renderContent();
    }

    renderAllDatasets() {
        const filtered = this.getFilteredAndSorted(this.datasets);
        document.getElementById('datasets-count').textContent = `${filtered.length} datasets`;
        
        // Show/hide active domain chip
        const chipContainer = document.getElementById('active-domain-chip-container');
        if (chipContainer) {
            if (this.activeDomain) {
                chipContainer.innerHTML = `
                    <div class="active-domain-chip">
                        Filtered: <strong>${this.activeDomain}</strong>
                        <button onclick="catalog.clearDomainFilter()" title="Clear filter">×</button>
                    </div>`;
            } else {
                chipContainer.innerHTML = '';
            }
        }

        const gridContainer = document.getElementById('all-datasets-grid');
        const listContainer = document.getElementById('all-datasets-list');
        
        if (this.currentView === 'grid') {
            this.renderCards(filtered, 'all-datasets-grid', 'dataset');
            gridContainer.classList.add('active');
            listContainer.classList.remove('active');
        } else {
            this.renderList(filtered, 'all-datasets-list', 'dataset');
            listContainer.classList.add('active');
            gridContainer.classList.remove('active');
        }
    }

    renderAllModels() {
        const filtered = this.getFilteredAndSorted(this.models);
        document.getElementById('models-count').textContent = `${filtered.length} models`;
        
        const gridContainer = document.getElementById('all-models-grid');
        const listContainer = document.getElementById('all-models-list');
        
        if (this.currentView === 'grid') {
            this.renderCards(filtered, 'all-models-grid', 'model');
            gridContainer.classList.add('active');
            listContainer.classList.remove('active');
        } else {
            this.renderList(filtered, 'all-models-list', 'model');
            listContainer.classList.add('active');
            gridContainer.classList.remove('active');
        }
    }

    getFilteredAndSorted(items) {
        let filtered = items;

        // Apply search filter
        if (this.searchQuery) {
            filtered = filtered.filter(item => {
                const searchableText = [
                    item.name,
                    item.domain,
                    item.description
                ].filter(Boolean).join(' ').toLowerCase();
                return searchableText.includes(this.searchQuery);
            });
        }

        // Apply active domain filter (set by domain explorer tiles)
        if (this.activeDomain && this.domainConfig) {
            filtered = filtered.filter(item => {
                return this.getDomainConfig(item.domain).category === this.activeDomain;
            });
        }

        // Apply sorting
        filtered = [...filtered].sort((a, b) => {
            switch (this.currentSort) {
                case 'domain':
                    return (a.domain || '').localeCompare(b.domain || '');
                case 'name':
                default:
                    return a.name.localeCompare(b.name);
            }
        });

        return filtered;
    }

    renderCards(items, containerId, type) {
        const container = document.getElementById(containerId);
        if (!container) return;

        if (items.length === 0) {
            container.innerHTML = '<div class="empty-state"><div class="empty-icon">🔍</div><div class="empty-title">No results found</div></div>';
            return;
        }

        container.innerHTML = items.map(item => this.createCard(item, type)).join('');
        
        // Add click handlers to cards
        container.querySelectorAll('.card').forEach(card => {
            card.addEventListener('click', () => {
                const id = card.dataset.id;
                const cardType = card.dataset.type;
                this.openModal(id, cardType);
            });
        });
    }

    createCard(item, type) {
        const isDataset = type === 'dataset';
        const bgClass = isDataset ? 'dataset-bg' : 'model-bg';
        
        let description = '';
        let domain = item.domain || 'Sensor';
        
        // Get domain configuration for background image
        const domainConfig = this.getDomainConfig(domain);
        const domainImage = domainConfig.image || '';
        const domainCategory = domainConfig.category || domain;
        
        if (isDataset) {
            // For datasets: create a comprehensive description from metadata
            const descParts = [];
            if (item.timePoints) descParts.push(`${item.timePoints} time points`);
            if (item.variables) descParts.push(item.variables);
            if (item.dimensions) descParts.push(`${item.dimensions} dimensions`);
            if (item.interval && item.interval !== 'Not specified') descParts.push(`Interval: ${item.interval}`);
            
            description = descParts.length > 0 
                ? descParts.join(' · ') 
                : this.truncateText(item.description || 'No description available', 80);
        } else {
            // For models: show datasets count and domains
            const domains = this.getModelDomains(item.name);
            const domainCount = domains.size;
            description = `Evaluated on ${item.datasetsCount || 0} datasets across ${domainCount} domain${domainCount !== 1 ? 's' : ''}`;
        }

        // Build background image style
        const backgroundStyle = domainImage ? `background-image: url('${domainImage}');` : '';

        return `
            <div class="card" data-id="${item.id}" data-type="${type}">
                <div class="card-image ${bgClass}" style="${backgroundStyle}">
                    <div class="card-meta">
                        <span class="meta-badge">${domainCategory}</span>
                    </div>
                </div>
                <div class="card-content">
                    <div class="card-title">${this.escapeHtml(item.name)}</div>
                    <div class="card-description">${this.escapeHtml(description)}</div>
                </div>
            </div>
        `;
    }

    renderList(items, containerId, type) {
        const container = document.getElementById(containerId);
        if (!container) return;

        if (items.length === 0) {
            container.innerHTML = '<div class="empty-state"><div class="empty-icon">🔍</div><div class="empty-title">No results found</div></div>';
            return;
        }

        container.innerHTML = items.map(item => this.createListItem(item, type)).join('');
        
        // Add click handlers to list items
        container.querySelectorAll('.list-item').forEach(item => {
            item.addEventListener('click', () => {
                const id = item.dataset.id;
                const itemType = item.dataset.type;
                this.openModal(id, itemType);
            });
        });
    }

    createListItem(item, type) {
        const isDataset = type === 'dataset';
        
        // Get domain configuration for background image
        let domain = item.domain || 'Sensor';
        const domainConfig = this.getDomainConfig(domain);
        const domainImage = domainConfig.image || '';
        const domainCategory = domainConfig.category || domain;
        
        // Build background image style for list icon
        const iconBackgroundStyle = domainImage ? `background-image: url('${domainImage}'); background-size: cover; background-position: center;` : '';
        
        if (isDataset) {
            // For datasets: show all metadata from spreadsheet
            const metaParts = [];
            
            if (item.timePoints) metaParts.push(`${item.timePoints} points`);
            if (item.variables) metaParts.push(item.variables);
            if (item.dimensions) metaParts.push(`${item.dimensions} dimensions`);
            
            const meta = metaParts.join(' · ');

            return `
                <div class="list-item" data-id="${item.id}" data-type="${type}">
                    <div class="list-icon" style="${iconBackgroundStyle}">
                    </div>
                    <div class="list-content">
                        <div class="list-title">${this.escapeHtml(item.name)}</div>
                        <div class="list-meta">${meta}</div>
                    </div>
                    <span class="list-badge">${this.escapeHtml(domainCategory)}</span>
                </div>
            `;
        } else {
            // For models: show more comprehensive information
            const totalDatasets = item.datasetsCount || 0;
            const domains = this.getModelDomains(item.name);
            const domainCount = domains.size;
            
            const meta = `Evaluated on ${totalDatasets} dataset${totalDatasets !== 1 ? 's' : ''} · ${domainCount} domain${domainCount !== 1 ? 's' : ''}`;
            const badge = domainCount > 0 ? `${domainCount} domain${domainCount !== 1 ? 's' : ''}` : 'Model';

            return `
                <div class="list-item" data-id="${item.id}" data-type="${type}">
                    <div class="list-icon" style="${iconBackgroundStyle}">
                    </div>
                    <div class="list-content">
                        <div class="list-title">${this.escapeHtml(item.name)}</div>
                        <div class="list-meta">${meta}</div>
                    </div>
                    <span class="list-badge">${badge}</span>
                </div>
            `;
        }
    }

    getModelDomains(modelName) {
        const domains = new Set();
        this.datasets.forEach(dataset => {
            if (dataset.benchmarks && dataset.benchmarks[modelName]) {
                if (dataset.domain) {
                    domains.add(dataset.domain);
                }
            }
        });
        return domains;
    }

    truncateText(text, maxLength) {
        if (!text) return '';
        if (text.length <= maxLength) return text;
        return text.substr(0, maxLength) + '...';
    }

    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    showError() {
        document.getElementById('loading').classList.add('hidden');
        document.getElementById('empty-state').classList.remove('hidden');
    }

    openModal(id, type) {
        let item;
        if (type === 'dataset') {
            item = this.datasets.find(d => d.id === id);
        } else {
            item = this.models.find(m => m.id === id);
        }

        if (!item) return;

        const modalBody = document.getElementById('modal-body');
        const modalTitle = document.getElementById('modal-title');
        
        modalTitle.textContent = item.name;
        modalBody.innerHTML = type === 'dataset' 
            ? this.createDatasetModalContent(item) 
            : this.createModelModalContent(item);

        // Add event listeners to benchmark badges if this is a dataset modal
        if (type === 'dataset') {
            const benchmarkBadges = modalBody.querySelectorAll('.benchmark-badge.clickable');
            benchmarkBadges.forEach(badge => {
                badge.addEventListener('click', () => {
                    const modelName = badge.dataset.modelName;
                    const modelId = badge.dataset.modelId;
                    const model = this.models.find(m => m.id === modelId);
                    if (model) {
                        this.openModal(modelId, 'model');
                    }
                });
                
                // Also support keyboard navigation
                badge.addEventListener('keypress', (e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        badge.click();
                    }
                });
            });
        }

        const modalOverlay = document.getElementById('modal-overlay');
        modalOverlay.classList.add('active');
        document.body.style.overflow = 'hidden';
    }

    closeModal() {
        const modalOverlay = document.getElementById('modal-overlay');
        modalOverlay.classList.remove('active');
        document.body.style.overflow = '';
    }

    createDatasetModalContent(dataset) {
        const benchmarksHTML = dataset.benchmarks ? this.createBenchmarksSection(dataset.benchmarks) : '';
        
        return `
            <div class="modal-section">
                <h3>Description</h3>
                <p class="modal-description">${this.escapeHtml(dataset.description || 'No description available.')}</p>
            </div>

            <div class="modal-section">
                <h3>Dataset Information</h3>
                <div class="modal-info-grid">
                    <div class="modal-info-item">
                        <span class="modal-info-label">Domain</span>
                        <span class="modal-info-value">${this.escapeHtml(dataset.domain || 'N/A')}</span>
                    </div>
                    <div class="modal-info-item">
                        <span class="modal-info-label">Time Points</span>
                        <span class="modal-info-value">${this.escapeHtml(dataset.timePoints || 'N/A')}</span>
                    </div>
                    <div class="modal-info-item">
                        <span class="modal-info-label">Interval</span>
                        <span class="modal-info-value">${this.escapeHtml(dataset.interval || 'N/A')}</span>
                    </div>
                    <div class="modal-info-item">
                        <span class="modal-info-label">Dimensions</span>
                        <span class="modal-info-value">${this.escapeHtml(dataset.dimensions || 'N/A')}</span>
                    </div>
                </div>
            </div>

            ${benchmarksHTML}

            ${dataset.paperLink || dataset.dataLink ? `
                <div class="modal-section">
                    <h3>Resources</h3>
                    <div class="modal-links">
                        ${dataset.paperLink ? `<a href="${this.escapeHtml(dataset.paperLink)}" target="_blank" class="modal-link">📄 View Paper</a>` : ''}
                        ${dataset.dataLink ? `<a href="${this.escapeHtml(dataset.dataLink)}" target="_blank" class="modal-link">📊 Access Data</a>` : ''}
                    </div>
                </div>
            ` : ''}
        `;
    }

    createModelModalContent(model) {
        // Get datasets that use this model
        const datasetsUsingModel = this.datasets.filter(d => 
            d.benchmarks && d.benchmarks[model.name]
        );

        return `
            <div class="modal-section">
                <h3>Model Description</h3>
                <p class="model-description-text">${this.escapeHtml(model.description || 'No description available.')}</p>
            </div>

            <div class="modal-section">
                <h3>Model Statistics</h3>
                <div class="model-stats-grid">
                    <div class="model-stat-card">
                        <div class="stat-number">${datasetsUsingModel.length}</div>
                        <div class="stat-label">Datasets Evaluated</div>
                    </div>
                    <div class="model-stat-card">
                        <div class="stat-number">${new Set(datasetsUsingModel.map(d => d.domain)).size}</div>
                        <div class="stat-label">Domains Covered</div>
                    </div>
                </div>
            </div>

            ${datasetsUsingModel.length > 0 ? `
                <div class="modal-section">
                    <h3>Datasets (${datasetsUsingModel.length})</h3>
                    <div class="sample-datasets-list scrollable">
                        ${datasetsUsingModel.map(d => `
                            <div class="sample-dataset-item">
                                <strong>${this.escapeHtml(d.name)}</strong>
                                <span class="dataset-domain-tag">${this.escapeHtml(d.domain || 'General')}</span>
                            </div>
                        `).join('')}
                    </div>
                </div>
            ` : ''}
        `;
    }

    createBenchmarksSection(benchmarks) {
        const modelNames = Object.keys(benchmarks);
        if (modelNames.length === 0) return '';

        return `
            <div class="modal-section">
                <h3>Evaluated Models</h3>
                <div class="benchmarks-grid">
                    ${modelNames.map(modelName => {
                        const isEvaluated = benchmarks[modelName];
                        const modelId = modelName.toLowerCase().replace(/\s+/g, '-');
                        return `<div class="benchmark-badge ${isEvaluated ? 'clickable' : 'inactive'}" 
                                     data-model-name="${this.escapeHtml(modelName)}" 
                                     data-model-id="${modelId}"
                                     ${isEvaluated ? 'role="button" tabindex="0"' : ''}>${this.escapeHtml(modelName)}</div>`;
                    }).join('')}
                </div>
            </div>
        `;
    }
}

// Initialize the catalog when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    new NotebookCatalog();
});
