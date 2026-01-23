/**
 * Time Series Commons - NotebookLM-Style Interface
 * Models and Datasets Catalog
 */

class NotebookCatalog {
    constructor() {
        this.allData = [];
        this.datasets = [];
        this.models = [];
        this.currentTab = 'all';
        this.currentView = 'list';
        this.currentSort = 'name';
        this.searchQuery = '';
        
        this.init();
    }

    async init() {
        try {
            await this.loadData();
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

    processData() {
        // Separate datasets and extract unique models
        this.datasets = this.allData;
        
        // Extract unique models from benchmarks
        const modelsSet = new Set();
        this.allData.forEach(dataset => {
            if (dataset.benchmarks) {
                Object.keys(dataset.benchmarks).forEach(modelName => {
                    if (dataset.benchmarks[modelName]) {
                        modelsSet.add(modelName);
                    }
                });
            }
        });

        // Create model objects with counts and descriptions
        this.models = Array.from(modelsSet).map(modelName => {
            const datasetsCount = this.allData.filter(d => 
                d.benchmarks && d.benchmarks[modelName]
            ).length;
            
            return {
                id: modelName.toLowerCase().replace(/\s+/g, '-'),
                name: modelName,
                type: 'model',
                datasetsCount: datasetsCount,
                description: this.getModelDescription(modelName)
            };
        });
    }

    getModelDescription(modelName) {
        const descriptions = {
            'Darts': 'Darts (Data Analysis and Real-Time Systems) is a Python library for time series forecasting developed by Unit8. It offers a unified interface for multiple forecasting models including statistical methods (ARIMA, ETS), machine learning approaches (Random Forests, LightGBM), and deep learning models (N-BEATS, Transformer). Darts supports both univariate and multivariate forecasting, handles covariates, and provides probabilistic forecasting capabilities with confidence intervals.',
            'Merlion': 'Merlion is a Python library for time series intelligence developed by Salesforce Research. It provides a unified interface for time series forecasting, anomaly detection, and change point detection. Merlion includes implementations of state-of-the-art algorithms including ARIMA, Prophet, LSTM, Transformer models, and ensemble methods. It emphasizes production-ready deployment with automatic hyperparameter tuning and model selection.',
            'Aeon': 'Aeon (formerly sktime) is a scikit-learn compatible Python toolkit for time series analysis. It provides a comprehensive suite of algorithms for time series classification, regression, clustering, and annotation. Aeon includes distance-based methods, shapelet transforms, dictionary-based approaches, and deep learning models. It emphasizes composability and modularity, allowing users to build complex pipelines.',
            'UCR': 'The UCR Time Series Classification Archive is the largest public repository of time series classification datasets. Maintained by the University of California, Riverside, it serves as the standard benchmark for evaluating time series classification algorithms. The archive includes diverse datasets from various domains and has been instrumental in advancing time series mining research since its inception.',
            'LPTM-Eval': 'LPTM-Eval (Large Pre-trained Time series Models Evaluation) is a comprehensive evaluation framework for assessing pre-trained time series foundation models. It provides standardized benchmarks across multiple tasks including forecasting, classification, and anomaly detection. LPTM-Eval enables fair comparison of different pre-training strategies and model architectures on diverse time series datasets.',
            'TS2Vec-Bench': 'TS2Vec-Bench is an evaluation framework specifically designed for time series representation learning methods. It assesses the quality of learned representations through downstream tasks like classification and clustering. TS2Vec (Time Series to Vector) focuses on contrastive learning approaches that learn universal representations without task-specific labels.',
            'Timer-XL': 'Timer-XL is a large-scale time series foundation model designed for cross-domain time series forecasting. It employs transformer architecture with innovations in tokenization and positional encoding tailored for time series. Timer-XL is pre-trained on extensive datasets and demonstrates strong transfer learning capabilities across different domains and forecast horizons.',
            'AutoGluon': 'AutoGluon-TimeSeries is an AutoML toolkit that automatically trains and ensembles multiple forecasting models. Developed by Amazon, it simplifies time series forecasting by automating model selection, hyperparameter tuning, and ensemble construction. AutoGluon combines statistical models (ETS, ARIMA), tree-based methods (CatBoost, LightGBM), and deep learning approaches.',
            'GluonTS': 'GluonTS is a Python toolkit for probabilistic time series modeling built on Apache MXNet and PyTorch. Developed by Amazon, it focuses on deep learning-based forecasting with neural architectures like DeepAR, Transformer, and temporal convolutional networks. GluonTS emphasizes probabilistic forecasts with proper uncertainty quantification.',
            'Monash': 'The Monash Time Series Forecasting Archive is a comprehensive collection of time series forecasting datasets from diverse domains. Maintained by Monash University, it complements existing archives with a focus on modern forecasting challenges including irregularly sampled data, missing values, and multi-horizon forecasting scenarios.',
            'NeuralProphet': 'NeuralProphet is a neural network-based time series forecasting library inspired by Facebook Prophet. It combines traditional time series decomposition with modern deep learning, offering interpretable forecasts through additive components (trend, seasonality, holidays). NeuralProphet supports autoregression, lagged regressors, and provides uncertainty estimates.',
            'PatchTST': 'PatchTST (Patch Time Series Transformer) is a transformer-based model that segments time series into patches for more efficient and effective forecasting. This patching mechanism reduces computational complexity while capturing both local and global patterns. PatchTST has demonstrated state-of-the-art performance on long-term forecasting benchmarks.',
            'Chronos': 'Chronos is a pre-trained probabilistic time series forecasting model developed by Amazon. It treats forecasting as a language modeling task, tokenizing time series and training transformer models on diverse datasets. Chronos demonstrates strong zero-shot forecasting capabilities across different domains and temporal granularities.',
            'Lag-Llama': 'Lag-Llama is a foundation model for time series forecasting that leverages large language model architectures. It uses a decoder-only transformer trained on extensive time series data to generate probabilistic forecasts. Lag-Llama excels at few-shot and zero-shot forecasting tasks across diverse domains.',
            'TimesFM': 'TimesFM (Time Series Foundation Model) is Google\'s pre-trained model for time series forecasting. It employs a patched-decoder architecture trained on a large corpus of real-world and synthetic time series. TimesFM provides zero-shot forecasting capabilities and demonstrates strong performance across various forecasting horizons.',
            'Moirai': 'Moirai is a universal time series forecasting model developed by Salesforce. It uses a unified architecture capable of handling any-variate (univariate or multivariate) time series with any frequency. Moirai is pre-trained on diverse datasets and supports flexible forecasting horizons.',
            'Moment': 'Moment (MOdel for Time series) is a family of foundation models for time series analysis. It supports multiple tasks including forecasting, classification, and anomaly detection through a single pre-trained model. Moment uses masked time series modeling as its pre-training objective.',
            'Nixtla': 'Nixtla provides production-ready time series forecasting solutions including StatsForecast (statistical models), MLForecast (machine learning), and NeuralForecast (deep learning). Their libraries emphasize scalability, accuracy, and ease of deployment for real-world forecasting applications.',
            'TSLib': 'TSLib (Time Series Library) is a comprehensive toolkit providing implementations of state-of-the-art time series forecasting models. It includes classic methods, modern deep learning approaches, and recent transformer-based architectures. TSLib emphasizes reproducible research with standardized experimental protocols.',
            'Informer': 'Informer is an efficient transformer model designed for long sequence time series forecasting (LSTF). It introduces ProbSparse self-attention mechanism and self-attention distilling to reduce computational complexity. Informer addresses the quadratic complexity issue of vanilla transformers for long sequences.',
            'Autoformer': 'Autoformer is a transformer variant that incorporates decomposition architecture and Auto-Correlation mechanism. It explicitly decomposes time series into trend and seasonal components, applying different transformations to each. This design improves long-term forecasting accuracy and interpretability.',
            'FEDformer': 'FEDformer (Frequency Enhanced Decomposed Transformer) performs forecasting in the frequency domain using Fourier and Wavelet transforms. This frequency-based approach captures long-term dependencies more efficiently than time-domain attention, achieving strong performance on long-term forecasting tasks.',
            'Pyraformer': 'Pyraformer introduces a pyramidal attention module with inter-scale tree structure to capture temporal dependencies at multiple resolutions. This hierarchical design reduces complexity while modeling both short-term and long-term patterns effectively for time series forecasting.',
            'MICN': 'MICN (Multi-scale Isometric Convolution Network) is a pure convolutional model for time series forecasting. It uses isometric convolutions at multiple scales to capture local and global temporal patterns. MICN demonstrates that well-designed convolutions can match transformer performance.',
            'DLinear': 'DLinear (Decomposition Linear) is a simple yet effective baseline that uses linear layers combined with trend-seasonal decomposition. Despite its simplicity, DLinear outperforms many complex deep learning models on long-term forecasting benchmarks, questioning the necessity of complex architectures.',
            'NLinear': 'NLinear (Normalization Linear) is an extremely simple baseline consisting of a single linear layer with instance normalization. It has shown competitive performance against complex models, highlighting the importance of proper normalization and questioning architectural complexity.',
            'RLinear': 'RLinear (Revin Linear) incorporates reversible instance normalization (RevIN) with linear layers for forecasting. The normalization-denormalization framework helps the model adapt to distribution shifts, achieving strong performance with minimal parameters.',
            'TiDE': 'TiDE (Time series Dense Encoder) is an MLP-based model that uses dense encoder-decoder architecture for multivariate forecasting. It explicitly models both past time series and future covariates through separate encoders, achieving competitive accuracy with high computational efficiency.',
            'FreTS': 'FreTS (Frequency-domain Transformer for Time Series) performs forecasting entirely in the frequency domain using complex-valued networks. This approach captures periodic patterns and long-range dependencies more naturally than time-domain models.',
            'TimesNet': 'TimesNet transforms 1D time series into 2D tensors to capture intra-period and inter-period variations simultaneously. It uses 2D convolutions (inception blocks) for this multi-periodicity modeling, achieving state-of-the-art results across multiple time series tasks.',
            'ETSformer': 'ETSformer combines the principles of exponential smoothing with transformer architecture. It decomposes forecasting into level, growth, and seasonal components, learning their interactions through attention mechanisms. This design provides both accuracy and interpretability.',
            'Crossformer': 'Crossformer introduces Dimension-Segment-Wise (DSW) structure to capture cross-dimension dependencies in multivariate time series. It uses two-stage attention for efficient modeling of both temporal and variate patterns.',
            'SegRNN': 'SegRNN (Segment RNN) processes time series in segments rather than point-by-point, improving efficiency and long-range modeling. It uses RNN cells (LSTM/GRU) on segmented data, achieving competitive performance with lower complexity.',
            'Transformer': 'The Vanilla Transformer applies the original attention mechanism from natural language processing to time series. While it demonstrates the potential of attention for sequential modeling, vanilla transformers face efficiency challenges with long time series.',
            'Non-stationary Transformer': 'Non-stationary Transformer addresses distribution shift in time series by de-stationary attention and series stationarization. It explicitly accounts for non-stationarity in both attention computation and normalization.',
            'iTransformer': 'iTransformer (Inverted Transformer) applies attention on the variate dimension rather than the temporal dimension for multivariate forecasting. This inversion improves performance by treating each variate as a token, capturing cross-variate dependencies.',
            'Reformer': 'Reformer uses locality-sensitive hashing to reduce transformer complexity from O(L²) to O(L log L). It makes transformers more practical for long sequences while maintaining modeling capacity.',
            'Flowformer': 'Flowformer replaces softmax attention with linear attention using flow formulation. This modification reduces computational cost while maintaining competitive accuracy for long sequence forecasting.',
            'Flashformer': 'Flashformer accelerates transformer training and inference using memory-efficient attention computation. It optimizes GPU memory usage and computation, enabling training on longer sequences.',
            'SparseTSF': 'SparseTSF (Sparse Time Series Forecasting) uses sparse attention patterns tailored for time series. It identifies and focuses on the most relevant historical time steps, reducing computation while maintaining accuracy.',
            'TSMixer': 'TSMixer uses MLP-Mixer architecture adapted for time series, mixing information across both time and feature dimensions with simple MLPs. It achieves strong performance with high computational efficiency.',
            'FITS': 'FITS (Frequency Interpolation Time Series) performs forecasting by interpolation in the frequency domain. It models frequency components directly, providing an efficient alternative to time-domain methods.',
            'SCINet': 'SCINet (Sample Convolution and Interaction Network) uses downsampling and interactive learning to capture temporal patterns at multiple resolutions. Its recursive structure models both short and long-term dependencies.',
            'LightTS': 'LightTS is a lightweight model using continuous wavelet transform and simple MLPs. It achieves strong forecasting performance with minimal parameters and computation.',
            'STEMGNN': 'STEMGNN (Spectro-Temporal Graph Neural Network) combines graph structure for spatial dependencies with spectral analysis for temporal patterns in multivariate time series.',
            'TCN': 'TCN (Temporal Convolutional Network) uses dilated causal convolutions to capture long-range dependencies. It provides an efficient alternative to RNNs with better parallelization.',
            'TimeMixer': 'TimeMixer employs multi-scale mixing for both past and future information. It decomposes time series at multiple scales and learns their interactions for improved forecasting.',
            'TSMixerx': 'TSMixerx extends TSMixer with enhanced mixing mechanisms and additional architectural improvements for better handling of complex temporal patterns.',
            'RITS': 'RITS (Recurrent Imputation for Time Series) handles missing values in time series through recurrent neural networks. It jointly performs imputation and forecasting.',
            'SAITS': 'SAITS (Self-Attention Imputation for Time Series) uses bidirectional self-attention for missing value imputation. It outperforms traditional imputation methods by leveraging temporal dependencies.',
            'GPVAE': 'GPVAE (Gaussian Process VAE) combines Gaussian processes with variational autoencoders for probabilistic time series modeling and imputation.',
            'BRITS': 'BRITS (Bidirectional Recurrent Imputation for Time Series) uses bidirectional RNNs to impute missing values considering both past and future context.',
            'ImputeFormer': 'ImputeFormer applies transformer architecture specifically for time series imputation. It uses masked self-attention to reconstruct missing values from observed ones.',
            'UniTS': 'UniTS (Universal Time Series model) is a unified model capable of handling multiple time series tasks including forecasting, classification, and imputation through a single architecture.',
            'NBEATS': 'N-BEATS (Neural Basis Expansion Analysis for Time Series) is a deep learning architecture based on backward and forward residual links. It decomposes forecasts into interpretable trend and seasonality components.',
            'NHITS': 'N-HiTS (Neural Hierarchical Interpolation for Time Series) extends N-BEATS with multi-rate sampling and hierarchical interpolation. It achieves better long-horizon accuracy and efficiency.',
            'TSLib-Forecasting': 'TSLib-Forecasting is a comprehensive library providing standardized implementations of time series forecasting models for benchmarking and research.',
            'LSTM': 'LSTM (Long Short-Term Memory) is a recurrent neural network architecture designed to capture long-term dependencies in sequences. It addresses the vanishing gradient problem through gating mechanisms.',
            'DeepAR': 'DeepAR is Amazon\'s autoregressive recurrent network for probabilistic forecasting. It learns across related time series and provides quantile forecasts for uncertainty estimation.',
            'Prophet': 'Prophet is Facebook\'s forecasting tool based on additive decomposition of trend, seasonality, and holidays. It\'s designed for business forecasting with strong out-of-the-box performance.',
            'ARIMA': 'ARIMA (AutoRegressive Integrated Moving Average) is a classical statistical model for time series forecasting. It models linear dependencies using autoregression, differencing for stationarity, and moving averages.',
            'ETS': 'ETS (Error, Trend, Seasonality) is a state space approach to forecasting that models level, trend, and seasonal components with exponential smoothing.',
            'Theta': 'Theta method decomposes time series into two theta-lines combining trend and seasonality. Despite its simplicity, it has won forecasting competitions.',
            'tbats': 'TBATS (Trigonometric seasonality, Box-Cox transformation, ARMA errors, Trend, Seasonal components) handles multiple seasonal patterns and complex seasonality.',
            'catboost': 'CatBoost is a gradient boosting library that can be adapted for time series forecasting through feature engineering. It handles categorical features natively.',
            'RandomForest': 'Random Forest uses ensemble of decision trees for regression/classification. For time series, it requires careful feature engineering but can capture non-linear patterns.',
            'lightgbm': 'LightGBM is an efficient gradient boosting framework often used for time series through lag features and other engineered features.',
            'RNN': 'RNN (Recurrent Neural Network) processes sequences by maintaining hidden states. While foundational, vanilla RNNs suffer from vanishing gradients for long sequences.',
            'GRU': 'GRU (Gated Recurrent Unit) simplifies LSTM with fewer gates while maintaining similar performance. It\'s more computationally efficient than LSTM.',
            'VARMAX': 'VARMAX (Vector AutoRegression Moving Average with eXogenous variables) extends VAR to include moving average and exogenous variables for multivariate forecasting.',
            'VECM': 'VECM (Vector Error Correction Model) is used for cointegrated time series, capturing long-run equilibrium relationships between variables.'
        };
        
        return descriptions[modelName] || `${modelName} is a time series model used for forecasting and analysis tasks. It has been evaluated across multiple benchmark datasets to assess its performance on various forecasting scenarios.`;
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

        // Set default view: list for datasets/models tabs, keep current for 'all' tab (featured sections)
        if (tabName === 'datasets' || tabName === 'models') {
            this.switchView('list');
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
        } else if (this.currentTab === 'datasets') {
            this.renderAllDatasets();
        } else if (this.currentTab === 'models') {
            this.renderAllModels();
        }
    }

    renderFeatured() {
        // Render featured datasets (first 4)
        const featuredDatasets = this.getFilteredAndSorted(this.datasets).slice(0, 4);
        this.renderCards(featuredDatasets, 'featured-datasets-grid', 'dataset');

        // Render featured models (first 4)
        const featuredModels = this.getFilteredAndSorted(this.models).slice(0, 4);
        this.renderCards(featuredModels, 'featured-models-grid', 'model');
    }

    renderAllDatasets() {
        const filtered = this.getFilteredAndSorted(this.datasets);
        document.getElementById('datasets-count').textContent = `${filtered.length} datasets`;
        
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
        const icon = isDataset ? '📊' : '🤖';
        
        let description = '';
        let domain = item.domain || 'General';
        
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
            domain = 'General';
        }

        return `
            <div class="card" data-id="${item.id}" data-type="${type}">
                <div class="card-image ${bgClass}">
                    <div class="card-icon">${icon}</div>
                    <div class="card-meta">
                        <span class="meta-badge">${domain}</span>
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
        const icon = isDataset ? '📊' : '🤖';
        
        if (isDataset) {
            // For datasets: show all metadata from spreadsheet
            const metaParts = [];
            
            if (item.domain) metaParts.push(item.domain);
            if (item.timePoints) metaParts.push(`${item.timePoints} points`);
            if (item.variables) metaParts.push(item.variables);
            if (item.dimensions) metaParts.push(`${item.dimensions} dimensions`);
            
            const meta = metaParts.join(' · ');
            const domain = item.domain || 'General';

            return `
                <div class="list-item" data-id="${item.id}" data-type="${type}">
                    <div class="list-icon">
                        <span style="font-size: 24px;">${icon}</span>
                    </div>
                    <div class="list-content">
                        <div class="list-title">${this.escapeHtml(item.name)}</div>
                        <div class="list-meta">${meta}</div>
                    </div>
                    <span class="list-badge">${this.escapeHtml(item.interval || 'Not specified')}</span>
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
                    <div class="list-icon">
                        <span style="font-size: 24px;">${icon}</span>
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
