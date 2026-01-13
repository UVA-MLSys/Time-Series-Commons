/**
 * Time Series Commons - Models Catalog
 * Interactive models catalog with filtering, search, and modal details
 */

class ModelsCatalog {
    constructor() {
        this.allModels = [];
        this.filteredModels = [];
        this.filters = {
            search: '',
            domain: '',
            interval: '',
            benchmarks: new Set()
        };
        this.currentModalIndex = -1;
        this.currentView = 'grid'; // 'grid' or 'list'
        this.catalogType = 'datasets'; // 'datasets' or 'models'
        this.allModelInfo = []; // Will store unique models with their info
        
        this.init();
    }

    async init() {
        try {
            await this.loadModels();
            this.setupEventListeners();
            this.populateFilters();
            this.applyFilters();
            this.renderModels();
        } catch (error) {
            console.error('Error initializing models catalog:', error);
            this.showError('Failed to load models data. Please refresh the page.');
        }
    }

    async loadModels() {
        const response = await fetch('./data/models.json');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        this.allModels = data.models || [];
        this.filteredModels = [...this.allModels];
    }

    setupEventListeners() {
        // Catalog type toggle buttons (Datasets vs Models)
        const catalogTypeBtns = document.querySelectorAll('.catalog-type-btn');
        catalogTypeBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                const catalogType = btn.getAttribute('data-catalog-type');
                this.switchCatalogType(catalogType);
            });
        });

        // View toggle buttons
        const viewToggleBtns = document.querySelectorAll('.view-toggle-btn');
        viewToggleBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                const view = btn.getAttribute('data-view');
                this.switchView(view);
            });
        });

        // Search input with debouncing
        const searchInput = document.getElementById('search-input');
        if (searchInput) {
            let debounceTimer;
            searchInput.addEventListener('input', (e) => {
                clearTimeout(debounceTimer);
                debounceTimer = setTimeout(() => {
                    this.filters.search = e.target.value.toLowerCase();
                    this.applyFilters();
                    this.renderModels();
                }, 300);
            });
        }

        // Domain filter
        const domainFilter = document.getElementById('domain-filter');
        if (domainFilter) {
            domainFilter.addEventListener('change', (e) => {
                this.filters.domain = e.target.value;
                this.applyFilters();
                this.renderModels();
            });
        }

        // Interval filter
        const intervalFilter = document.getElementById('interval-filter');
        if (intervalFilter) {
            intervalFilter.addEventListener('change', (e) => {
                this.filters.interval = e.target.value;
                this.applyFilters();
                this.renderModels();
            });
        }

        // Modal close events
        const modalOverlay = document.getElementById('model-modal');
        const modalClose = document.getElementById('modal-close');
        
        if (modalOverlay) {
            modalOverlay.addEventListener('click', (e) => {
                if (e.target === modalOverlay) {
                    this.closeModal();
                }
            });
        }

        if (modalClose) {
            modalClose.addEventListener('click', () => this.closeModal());
        }

        // Model info modal close events
        const modelInfoOverlay = document.getElementById('model-info-modal');
        const modelInfoClose = document.getElementById('model-info-close');
        
        if (modelInfoOverlay) {
            modelInfoOverlay.addEventListener('click', (e) => {
                if (e.target === modelInfoOverlay) {
                    this.closeModelInfoModal();
                }
            });
        }

        if (modelInfoClose) {
            modelInfoClose.addEventListener('click', () => this.closeModelInfoModal());
        }

        // Keyboard events
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.closeModal();
                this.closeModelInfoModal();
            }
        });

        // Smooth scroll for navigation
        document.querySelectorAll('a[href^="#"]').forEach(anchor => {
            anchor.addEventListener('click', function (e) {
                const href = this.getAttribute('href');
                if (href !== '#') {
                    e.preventDefault();
                    const target = document.querySelector(href);
                    if (target) {
                        target.scrollIntoView({
                            behavior: 'smooth',
                            block: 'start'
                        });
                    }
                }
            });
        });
    }

    populateFilters() {
        // Populate domain filter
        const domains = new Set();
        this.allModels.forEach(model => {
            if (model.domain && model.domain.trim()) {
                model.domain.split(',').forEach(d => {
                    const trimmed = d.trim();
                    if (trimmed && trimmed !== 'Not Available') {
                        domains.add(trimmed);
                    }
                });
            }
        });

        const domainFilter = document.getElementById('domain-filter');
        if (domainFilter) {
            Array.from(domains).sort().forEach(domain => {
                const option = document.createElement('option');
                option.value = domain;
                option.textContent = domain;
                domainFilter.appendChild(option);
            });
        }

        // Populate model filters - get ALL unique model names from benchmarks
        const modelFiltersContainer = document.getElementById('model-filters');
        if (modelFiltersContainer) {
            // Collect all unique model/benchmark names across all datasets
            const allModels = new Set();
            this.allModels.forEach(model => {
                if (model.benchmarks && typeof model.benchmarks === 'object') {
                    Object.keys(model.benchmarks).forEach(modelName => {
                        if (modelName && modelName.trim()) {
                            allModels.add(modelName.trim());
                        }
                    });
                }
            });

            // Sort alphabetically and create filter items
            Array.from(allModels).sort().forEach(modelName => {
                const filterItem = document.createElement('div');
                filterItem.className = 'model-filter-item';
                filterItem.innerHTML = `
                    <input type="checkbox" id="model-${this.escapeHtml(modelName)}" value="${this.escapeHtml(modelName)}">
                    <label for="model-${this.escapeHtml(modelName)}">${this.escapeHtml(modelName)}</label>
                `;
                
                const checkbox = filterItem.querySelector('input');
                checkbox.addEventListener('change', (e) => {
                    if (e.target.checked) {
                        this.filters.benchmarks.add(modelName);
                        filterItem.classList.add('active');
                    } else {
                        this.filters.benchmarks.delete(modelName);
                        filterItem.classList.remove('active');
                    }
                    this.applyFilters();
                    this.renderModels();
                    this.updateActiveFiltersDisplay();
                });

                modelFiltersContainer.appendChild(filterItem);
            });
        }
    }

    applyFilters() {
        this.filteredModels = this.allModels.filter(model => {
            // Search filter
            if (this.filters.search) {
                const searchLower = this.filters.search;
                const name = (model.name || '').toLowerCase();
                const description = (model.description || '').toLowerCase();
                const domain = (model.domain || '').toLowerCase();
                
                const matchesSearch = 
                    name.includes(searchLower) ||
                    description.includes(searchLower) ||
                    domain.includes(searchLower);
                
                if (!matchesSearch) return false;
            }

            // Domain filter
            if (this.filters.domain) {
                const modelDomain = model.domain || '';
                if (!modelDomain.includes(this.filters.domain)) {
                    return false;
                }
            }

            // Interval filter
            if (this.filters.interval) {
                const interval = (model.interval || '').toLowerCase();
                const filterValue = this.filters.interval.toLowerCase();
                if (!interval.includes(filterValue)) {
                    return false;
                }
            }

            // Benchmark filter
            if (this.filters.benchmarks.size > 0) {
                const modelBenchmarks = Object.keys(model.benchmarks || {});
                const hasAnyBenchmark = Array.from(this.filters.benchmarks).some(
                    benchmark => modelBenchmarks.includes(benchmark)
                );
                if (!hasAnyBenchmark) {
                    return false;
                }
            }

            return true;
        });

        this.updateActiveFiltersDisplay();
    }

    updateActiveFiltersDisplay() {
        const container = document.getElementById('active-filters');
        if (!container) return;

        container.innerHTML = '';
        let hasFilters = false;

        // Search filter tag
        if (this.filters.search) {
            hasFilters = true;
            container.appendChild(this.createFilterTag('Search', this.filters.search, () => {
                document.getElementById('search-input').value = '';
                this.filters.search = '';
                this.applyFilters();
                this.renderModels();
            }));
        }

        // Domain filter tag
        if (this.filters.domain) {
            hasFilters = true;
            container.appendChild(this.createFilterTag('Domain', this.filters.domain, () => {
                document.getElementById('domain-filter').value = '';
                this.filters.domain = '';
                this.applyFilters();
                this.renderModels();
            }));
        }

        // Interval filter tag
        if (this.filters.interval) {
            hasFilters = true;
            container.appendChild(this.createFilterTag('Interval', this.filters.interval, () => {
                document.getElementById('interval-filter').value = '';
                this.filters.interval = '';
                this.applyFilters();
                this.renderModels();
            }));
        }

        // Model filter tags
        this.filters.benchmarks.forEach(modelName => {
            hasFilters = true;
            container.appendChild(this.createFilterTag('Model', modelName, () => {
                this.filters.benchmarks.delete(modelName);
                const checkbox = document.getElementById(`model-${modelName}`);
                if (checkbox) {
                    checkbox.checked = false;
                    checkbox.closest('.model-filter-item').classList.remove('active');
                }
                this.applyFilters();
                this.renderModels();
            }));
        });

        // Clear all button
        if (hasFilters) {
            const clearAll = document.createElement('button');
            clearAll.className = 'clear-all-filters';
            clearAll.textContent = 'Clear All';
            clearAll.addEventListener('click', () => this.clearAllFilters());
            container.appendChild(clearAll);
        }
    }

    createFilterTag(label, value, onRemove) {
        const tag = document.createElement('div');
        tag.className = 'filter-tag';
        tag.innerHTML = `
            <span>${label}: ${value}</span>
            <span class="remove-filter" aria-label="Remove filter">&times;</span>
        `;
        tag.querySelector('.remove-filter').addEventListener('click', onRemove);
        return tag;
    }

    clearAllFilters() {
        // Clear search
        const searchInput = document.getElementById('search-input');
        if (searchInput) searchInput.value = '';
        this.filters.search = '';

        // Clear domain
        const domainFilter = document.getElementById('domain-filter');
        if (domainFilter) domainFilter.value = '';
        this.filters.domain = '';

        // Clear interval
        const intervalFilter = document.getElementById('interval-filter');
        if (intervalFilter) intervalFilter.value = '';
        this.filters.interval = '';

        // Clear model filters
        this.filters.benchmarks.clear();
        document.querySelectorAll('.model-filter-item').forEach(item => {
            item.classList.remove('active');
            const checkbox = item.querySelector('input[type="checkbox"]');
            if (checkbox) checkbox.checked = false;
        });

        this.applyFilters();
        this.renderModels();
    }

    switchView(view) {
        this.currentView = view;
        
        // Update button states
        document.querySelectorAll('.view-toggle-btn').forEach(btn => {
            if (btn.getAttribute('data-view') === view) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });

        // Show/hide appropriate containers
        const grid = document.getElementById('models-grid');
        const list = document.getElementById('models-list');
        
        if (view === 'grid') {
            if (grid) grid.classList.remove('hidden');
            if (list) list.classList.add('hidden');
        } else {
            if (grid) grid.classList.add('hidden');
            if (list) list.classList.remove('hidden');
        }

        this.renderModels();
    }

    switchCatalogType(catalogType) {
        this.catalogType = catalogType;
        
        // Update button states
        document.querySelectorAll('.catalog-type-btn').forEach(btn => {
            if (btn.getAttribute('data-catalog-type') === catalogType) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });

        // Update results type label
        const resultsType = document.getElementById('results-type');
        if (resultsType) {
            resultsType.textContent = catalogType;
        }

        // Re-render the catalog
        this.renderModels();
    }

    renderModels() {
        // Check if we should render model cards instead of dataset cards
        if (this.catalogType === 'models') {
            this.renderModelsView();
            return;
        }

        const grid = document.getElementById('models-grid');
        const list = document.getElementById('models-list');
        const noResults = document.getElementById('no-results');
        const resultsCount = document.getElementById('results-count');

        // Update results count
        if (resultsCount) {
            resultsCount.textContent = this.filteredModels.length;
        }

        // Clear both containers
        if (grid) grid.innerHTML = '';
        if (list) list.innerHTML = '';

        // Show/hide no results message
        if (this.filteredModels.length === 0) {
            if (noResults) noResults.classList.remove('hidden');
            return;
        } else {
            if (noResults) noResults.classList.add('hidden');
        }

        // Render based on current view
        if (this.currentView === 'grid') {
            this.renderGridView();
        } else {
            this.renderListView();
        }
    }

    renderGridView() {
        const grid = document.getElementById('models-grid');
        if (!grid) return;

        this.filteredModels.forEach((model, index) => {
            const card = this.createModelCard(model, index);
            grid.appendChild(card);
        });
    }

    renderListView() {
        const list = document.getElementById('models-list');
        if (!list) return;

        this.filteredModels.forEach((model, index) => {
            const listItem = this.createListItem(model, index);
            list.appendChild(listItem);
        });
    }

    createModelCard(model, index) {
        const card = document.createElement('div');
        card.className = 'model-card';
        
        // Truncate description
        const maxDescLength = 150;
        let description = (model.description && model.description.trim()) ? model.description : 'Not Available';
        if (description !== 'Not Available' && description.length > maxDescLength) {
            description = description.substring(0, maxDescLength) + '...';
        }

        // Get primary domain
        const primaryDomain = (model.domain && model.domain.trim()) ? model.domain.split(',')[0].trim() : 'Not Available';

        // Count active benchmarks
        const benchmarkCount = Object.keys(model.benchmarks || {}).length;

        // Display values or "Not Available"
        const variables = (model.variables && model.variables.trim()) ? model.variables : 'Not Available';
        const timePoints = (model.timePoints && model.timePoints.trim()) ? model.timePoints : 'Not Available';
        const interval = (model.interval && model.interval.trim()) ? model.interval : 'Not Available';

        card.innerHTML = `
            <div class="model-card-header">
                <h3>${this.escapeHtml(model.name || 'Unnamed Dataset')}</h3>
                <span class="model-domain">${this.escapeHtml(primaryDomain)}</span>
            </div>
            <div class="model-stats">
                <div class="stat-item">
                    <span class="stat-label">Variables:</span>
                    <span class="stat-value">${this.escapeHtml(variables)}</span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">Time Points:</span>
                    <span class="stat-value">${this.escapeHtml(timePoints)}</span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">Interval:</span>
                    <span class="stat-value">${this.escapeHtml(interval)}</span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">Benchmarks:</span>
                    <span class="stat-value">${benchmarkCount}</span>
                </div>
            </div>
            <div class="model-description">
                ${this.escapeHtml(description)}
            </div>
            <button class="view-details-btn">View Details</button>
        `;

        card.querySelector('.view-details-btn').addEventListener('click', () => {
            this.openModal(model, index);
        });

        return card;
    }

    createListItem(model, index) {
        const item = document.createElement('div');
        item.className = 'model-list-item';
        
        // Truncate description for list view
        const maxDescLength = 200;
        let description = (model.description && model.description.trim()) ? model.description : 'Not Available';
        if (description !== 'Not Available' && description.length > maxDescLength) {
            description = description.substring(0, maxDescLength) + '...';
        }

        // Get primary domain
        const primaryDomain = (model.domain && model.domain.trim()) ? model.domain.split(',')[0].trim() : 'Not Available';

        // Format interval for display
        const interval = (model.interval && model.interval.trim()) ? model.interval : 'Not Available';
        const intervalShort = interval !== 'Not Available' && interval.length > 30 ? interval.substring(0, 30) + '...' : interval;

        // Display values or "Not Available"
        const variables = (model.variables && model.variables.trim()) ? model.variables : 'Not Available';
        const timePoints = (model.timePoints && model.timePoints.trim()) ? model.timePoints : 'Not Available';

        item.innerHTML = `
            <div class="model-list-item-content">
                <h3>
                    ${this.escapeHtml(model.name || 'Unnamed Dataset')}
                    <span class="model-domain">${this.escapeHtml(primaryDomain)}</span>
                </h3>
                <div class="model-list-item-description">
                    ${this.escapeHtml(description)}
                </div>
                <div class="model-list-item-meta">
                    <span><strong>Variables:</strong> ${this.escapeHtml(variables)}</span>
                    <span><strong>Time Points:</strong> ${this.escapeHtml(timePoints)}</span>
                    <span><strong>Interval:</strong> ${this.escapeHtml(intervalShort)}</span>
                </div>
            </div>
            <div class="model-list-item-arrow">→</div>
        `;

        item.addEventListener('click', () => {
            this.openModal(model, index);
        });

        return item;
    }

    isValidUrl(string) {
        if (!string || !string.trim()) return false;
        try {
            const url = new URL(string.trim());
            return url.protocol === 'http:' || url.protocol === 'https:';
        } catch (_) {
            return false;
        }
    }

    renderModelsView() {
        const grid = document.getElementById('models-grid');
        const list = document.getElementById('models-list');
        const noResults = document.getElementById('no-results');
        const resultsCount = document.getElementById('results-count');

        // Extract all unique models from datasets
        const modelsSet = new Set();
        this.allModels.forEach(dataset => {
            if (dataset.benchmarks) {
                Object.keys(dataset.benchmarks).forEach(model => {
                    if (dataset.benchmarks[model]) {
                        modelsSet.add(model);
                    }
                });
            }
        });

        const uniqueModels = Array.from(modelsSet).sort();

        // Update results count
        if (resultsCount) {
            resultsCount.textContent = uniqueModels.length;
        }

        // Clear both containers
        if (grid) grid.innerHTML = '';
        if (list) list.innerHTML = '';

        // Show/hide no results message
        if (uniqueModels.length === 0) {
            if (noResults) noResults.classList.remove('hidden');
            return;
        } else {
            if (noResults) noResults.classList.add('hidden');
        }

        // Render models based on current view
        if (this.currentView === 'grid') {
            uniqueModels.forEach(modelName => {
                const card = this.createModelInfoCard(modelName);
                if (grid) grid.appendChild(card);
            });
        } else {
            uniqueModels.forEach(modelName => {
                const item = this.createModelInfoListItem(modelName);
                if (list) list.appendChild(item);
            });
        }
    }

    createModelInfoCard(modelName) {
        const modelInfo = this.getModelInfo(modelName);
        const card = document.createElement('div');
        card.className = 'model-card model-info-card-display';

        card.innerHTML = `
            <div class="model-card-header">
                <h3>${this.escapeHtml(modelInfo.name)}</h3>
                <span class="model-badge-large">${this.escapeHtml(modelInfo.architecture)}</span>
            </div>
            <div class="model-meta-row">
                <span class="meta-badge">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="12" r="10"></circle>
                        <polyline points="12 6 12 12 16 14"></polyline>
                    </svg>
                    ${this.escapeHtml(modelInfo.year)}
                </span>
                <span class="meta-badge">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
                        <circle cx="9" cy="7" r="4"></circle>
                        <path d="M23 21v-2a4 4 0 0 0-3-3.87"></path>
                        <path d="M16 3.13a4 4 0 0 1 0 7.75"></path>
                    </svg>
                    ${this.escapeHtml(modelInfo.developer)}
                </span>
            </div>
            <div class="model-description">
                ${this.escapeHtml(modelInfo.shortDesc)}
            </div>
            <div class="model-stats">
                <div class="stat-item">
                    <span class="stat-value">${modelInfo.datasetCount}</span>
                    <span class="stat-label">Datasets</span>
                </div>
                <div class="stat-item">
                    <span class="stat-value">${Math.round((modelInfo.datasetCount / this.allModels.length) * 100)}%</span>
                    <span class="stat-label">Coverage</span>
                </div>
            </div>
            <button class="view-details-btn">View Full Details</button>
        `;

        card.querySelector('.view-details-btn').addEventListener('click', () => {
            this.openModelInfoModal(modelName);
        });

        return card;
    }

    createModelInfoListItem(modelName) {
        const modelInfo = this.getModelInfo(modelName);
        const item = document.createElement('div');
        item.className = 'model-list-item model-info-list-display';

        item.innerHTML = `
            <div class="model-list-item-content">
                <h3>
                    ${this.escapeHtml(modelInfo.name)}
                    <span class="model-badge-inline">${this.escapeHtml(modelInfo.architecture)}</span>
                </h3>
                <div class="model-list-meta">
                    <span>${this.escapeHtml(modelInfo.year)}</span>
                    <span>•</span>
                    <span>${this.escapeHtml(modelInfo.developer)}</span>
                    <span>•</span>
                    <span>${modelInfo.datasetCount} datasets (${Math.round((modelInfo.datasetCount / this.allModels.length) * 100)}% coverage)</span>
                </div>
                <div class="model-list-item-description">
                    ${this.escapeHtml(modelInfo.shortDesc)}
                </div>
                <button class="view-details-btn-inline">View Full Details →</button>
            </div>
        `;

        item.addEventListener('click', () => {
            this.openModelInfoModal(modelName);
        });

        return item;
    }

    openModal(model, index) {
        this.currentModalIndex = index;
        const modal = document.getElementById('model-modal');
        const modalBody = document.getElementById('modal-body');
        const modalTitle = document.getElementById('modal-title');

        if (!modal || !modalBody || !modalTitle) return;

        modalTitle.textContent = model.name || 'Unnamed Dataset';

        // Explicitly check for data availability
        const domain = (model.domain && model.domain.trim()) ? model.domain : 'Not Available';
        const variables = (model.variables && model.variables.trim()) ? model.variables : 'Not Available';
        const timePoints = (model.timePoints && model.timePoints.trim()) ? model.timePoints : 'Not Available';
        const interval = (model.interval && model.interval.trim()) ? model.interval : 'Not Available';
        const repository = (model.repository && model.repository.trim()) ? model.repository : 'Not Available';
        const description = (model.description && model.description.trim()) ? model.description : '';
        const comments = (model.comments && model.comments.trim()) ? model.comments : '';
        
        // Validate links
        const dataLink = this.isValidUrl(model.dataLink) ? model.dataLink.trim() : null;
        const repositoryLink = this.isValidUrl(model.repository) ? model.repository.trim() : null;

        // Get active models/benchmarks for this dataset
        const activeModels = Object.keys(model.benchmarks || {}).filter(m => model.benchmarks[m]);
        
        // Create comprehensive modal content
        modalBody.innerHTML = `
            <div class="modal-section">
                <div class="modal-badges-container">
                    <span class="model-domain">${this.escapeHtml(domain)}</span>
                    ${activeModels.length > 0 ? `
                        <div class="modal-evaluated-models">
                            <span class="evaluated-label">Evaluated by:</span>
                            ${activeModels.map(modelName => `
                                <span class="model-badge clickable" data-model="${this.escapeHtml(modelName)}" title="Click to filter by ${this.escapeHtml(modelName)}">
                                    ${this.escapeHtml(modelName)}
                                </span>
                            `).join('')}
                        </div>
                    ` : ''}
                </div>
            </div>

            <div class="modal-section">
                <h3>Dataset Information</h3>
                <div class="modal-info-grid">
                    <div class="modal-info-item">
                        <span class="modal-info-label">Variables</span>
                        <span class="modal-info-value">${this.escapeHtml(variables)}</span>
                    </div>
                    <div class="modal-info-item">
                        <span class="modal-info-label">Time Points</span>
                        <span class="modal-info-value">${this.escapeHtml(timePoints)}</span>
                    </div>
                    <div class="modal-info-item">
                        <span class="modal-info-label">Time Interval</span>
                        <span class="modal-info-value">${this.escapeHtml(interval)}</span>
                    </div>
                    <div class="modal-info-item">
                        <span class="modal-info-label">Repository</span>
                        <span class="modal-info-value">${this.escapeHtml(repository)}</span>
                    </div>
                </div>
            </div>

            ${description ? `
                <div class="modal-section">
                    <h3>Description</h3>
                    <div class="modal-description">
                        ${this.escapeHtml(description)}
                    </div>
                </div>
            ` : ''}

            ${comments ? `
                <div class="modal-section">
                    <h3>Additional Information</h3>
                    <div class="modal-description">
                        ${this.escapeHtml(comments)}
                    </div>
                </div>
            ` : ''}

            ${(dataLink || repositoryLink) ? `
                <div class="modal-section">
                    <h3>Access Data</h3>
                    <div class="modal-links">
                        ${dataLink ? `<a href="${this.escapeHtml(dataLink)}" target="_blank" rel="noopener noreferrer" class="modal-link">📊 Dataset Link</a>` : ''}
                        ${repositoryLink && repositoryLink !== dataLink ? `<a href="${this.escapeHtml(repositoryLink)}" target="_blank" rel="noopener noreferrer" class="modal-link">📁 Repository</a>` : ''}
                    </div>
                </div>
            ` : `
                <div class="modal-section">
                    <h3>Access Data</h3>
                    <p style="color: #666; font-style: italic;">No valid links available for this dataset.</p>
                </div>
            `}

            <div class="modal-section">
                <h3>Benchmarks & Evaluations</h3>
                <div class="benchmarks-grid">
                    ${this.renderBenchmarksGrid(model.benchmarks)}
                </div>
            </div>
        `;

        // Add click handlers to model badges (both top badges and grid badges)
        const clickHandler = (e) => {
            const modelName = e.target.getAttribute('data-model');
            if (modelName) {
                // Open model information modal
                this.openModelInfoModal(modelName);
            }
        };
        
        modalBody.querySelectorAll('.model-badge.clickable').forEach(badge => {
            badge.addEventListener('click', clickHandler);
        });
        
        modalBody.querySelectorAll('.benchmark-badge.clickable-grid-badge').forEach(badge => {
            badge.addEventListener('click', clickHandler);
        });

        // Show modal with animation
        modal.classList.add('active');
        document.body.style.overflow = 'hidden'; // Prevent background scrolling
    }

    renderBenchmarksGrid(benchmarks) {
        const allBenchmarks = [
            'Informer', 'Monash TSER', 'UTSD', 'AutoGluon', 'Darts', 'TSLib',
            'Prophet', 'NeuralForecast', 'Merlion', 'Aeon', 'UCR', 'UEA',
            'Chronos-Pre', 'Chronos-Eval1', 'Chronos-Eval2', 'TimeGPT', 'Tempo',
            'TimesNet', 'TimesFM', 'Timer-XL', 'TSMamba-ZS', 'AutoTimes'
        ];

        return allBenchmarks.map(benchmark => {
            const isActive = benchmarks && benchmarks[benchmark];
            return `
                <div class="benchmark-badge ${isActive ? 'clickable-grid-badge' : 'inactive'}" ${isActive ? `data-model="${this.escapeHtml(benchmark)}" title="Click to filter by ${this.escapeHtml(benchmark)}"` : ''}>
                    ${isActive ? '✓ ' : ''}${benchmark}
                </div>
            `;
        }).join('');
    }

    closeModal() {
        const modal = document.getElementById('model-modal');
        if (modal) {
            modal.classList.remove('active');
            document.body.style.overflow = ''; // Restore scrolling
        }
    }

    getModelInfo(modelName) {
        // Count datasets that have this model in their benchmarks
        const datasetsEvaluated = this.allModels.filter(dataset => {
            return dataset.benchmarks && dataset.benchmarks[modelName];
        });

        const modelDesc = this.getModelDescription(modelName);

        return {
            name: modelName,
            datasetCount: datasetsEvaluated.length,
            datasets: datasetsEvaluated,
            shortDesc: modelDesc.shortDesc,
            fullDesc: modelDesc.fullDesc,
            architecture: modelDesc.architecture,
            year: modelDesc.year,
            developer: modelDesc.developer,
            keyFeatures: modelDesc.keyFeatures,
            useCases: modelDesc.useCases
        };
    }

    getModelDescription(modelName) {
        const descriptions = {
            'Informer': {
                shortDesc: 'A time series forecasting model that uses ProbSparse self-attention mechanism to capture long-range dependencies efficiently.',
                fullDesc: 'Informer is a transformer-based model specifically designed for long sequence time-series forecasting (LSTF). It addresses the limitations of vanilla transformers by introducing the ProbSparse self-attention mechanism, which dramatically reduces computational complexity from O(L²) to O(L log L). The model also features a self-attention distilling operation and a generative-style decoder to handle extremely long inputs and outputs efficiently.',
                architecture: 'Transformer with ProbSparse Attention',
                year: '2021',
                developer: 'Beihang University',
                keyFeatures: ['ProbSparse self-attention', 'Self-attention distilling', 'Generative decoder', 'Efficient long-sequence handling'],
                useCases: ['Long-term forecasting', 'Electricity consumption', 'Temperature prediction', 'Traffic flow']
            },
            'Prophet': {
                shortDesc: 'Facebook\'s forecasting tool designed for business time series that have strong seasonal effects and several seasons of historical data.',
                fullDesc: 'Prophet is a procedure for forecasting time series data based on an additive model where non-linear trends are fit with yearly, weekly, and daily seasonality, plus holiday effects. It works best with time series that have strong seasonal effects and several seasons of historical data. Prophet is robust to missing data and shifts in the trend, and typically handles outliers well.',
                architecture: 'Additive Regression Model',
                year: '2017',
                developer: 'Meta (Facebook)',
                keyFeatures: ['Automatic changepoint detection', 'Multiple seasonality handling', 'Holiday effects', 'Robust to missing data', 'Interpretable parameters'],
                useCases: ['Business forecasting', 'Sales prediction', 'Web traffic', 'Resource planning']
            },
            'TimeGPT': {
                shortDesc: 'A foundation model for time series forecasting that leverages large-scale pre-training on diverse temporal data.',
                fullDesc: 'TimeGPT is the first foundational model for time series forecasting, pre-trained on over 100 billion data points from diverse domains. It uses a transformer-based architecture with attention mechanisms optimized for temporal data. The model can perform zero-shot forecasting on new datasets without fine-tuning, making it highly versatile across different domains and frequencies.',
                architecture: 'Transformer-based Foundation Model',
                year: '2023',
                developer: 'Nixtla',
                keyFeatures: ['Zero-shot forecasting', 'Pre-trained on 100B+ data points', 'Multi-domain generalization', 'API-based deployment', 'Confidence intervals'],
                useCases: ['Cross-domain forecasting', 'Quick deployment', 'Limited training data scenarios', 'Production systems']
            },
            'Chronos-Pre': {
                shortDesc: 'Pre-training benchmark for Chronos, a language model-based approach to probabilistic time series forecasting.',
                fullDesc: 'Chronos is a framework that treats time series forecasting as a language modeling task. Time series values are scaled and quantized into discrete tokens, which are then processed by a pre-trained language model (T5). This approach allows Chronos to leverage the powerful pattern recognition capabilities of large language models for time series data. The pre-training phase uses a large corpus of diverse time series datasets.',
                architecture: 'T5 Language Model adapted for Time Series',
                year: '2024',
                developer: 'Amazon',
                keyFeatures: ['Language model tokenization', 'Probabilistic forecasting', 'Zero-shot capabilities', 'Multiple forecast horizons', 'Quantile predictions'],
                useCases: ['Probabilistic forecasting', 'Uncertainty quantification', 'Cross-domain applications', 'Risk assessment']
            },
            'Chronos-Eval1': {
                shortDesc: 'First evaluation benchmark set for the Chronos time series forecasting model.',
                fullDesc: 'The first comprehensive evaluation suite for Chronos models, testing performance across diverse datasets and forecasting horizons. This benchmark assesses the model\'s ability to generalize to unseen data patterns and domains without fine-tuning.',
                architecture: 'T5 Language Model adapted for Time Series',
                year: '2024',
                developer: 'Amazon',
                keyFeatures: ['Comprehensive evaluation', 'Multi-domain testing', 'Zero-shot performance metrics', 'Standardized benchmarking'],
                useCases: ['Model evaluation', 'Performance benchmarking', 'Cross-dataset comparison']
            },
            'Chronos-Eval2': {
                shortDesc: 'Second evaluation benchmark set for the Chronos time series forecasting model.',
                fullDesc: 'An extended evaluation suite for Chronos models, covering additional datasets and edge cases. This benchmark includes more challenging scenarios and longer forecast horizons to test model robustness.',
                architecture: 'T5 Language Model adapted for Time Series',
                year: '2024',
                developer: 'Amazon',
                keyFeatures: ['Extended evaluation', 'Edge case testing', 'Long-horizon forecasting', 'Robustness assessment'],
                useCases: ['Advanced model evaluation', 'Stress testing', 'Long-term forecasting assessment']
            },
            'AutoGluon': {
                shortDesc: 'AutoML toolkit for time series forecasting with automatic model selection and ensemble methods.',
                fullDesc: 'AutoGluon-TimeSeries is an AutoML framework that automates the process of building accurate time series forecasting models. It automatically trains and ensembles multiple models including statistical methods (ARIMA, ETS), classical ML models (LightGBM, CatBoost), and deep learning models (DeepAR, Temporal Fusion Transformer). The system performs automatic hyperparameter tuning and model selection based on validation performance.',
                architecture: 'Ensemble AutoML Framework',
                year: '2020 (Time series module: 2022)',
                developer: 'Amazon Web Services (AWS)',
                keyFeatures: ['Automatic model selection', 'Ensemble methods', 'Hyperparameter optimization', 'Multi-model training', 'Easy deployment'],
                useCases: ['Rapid prototyping', 'Non-expert usage', 'Production forecasting', 'Benchmark comparison']
            },
            'Darts': {
                shortDesc: 'A Python library for user-friendly forecasting and anomaly detection on time series.',
                fullDesc: 'Darts is a comprehensive Python library that makes it easy to forecast time series. It offers a wide range of models from classics like ARIMA to deep learning models like N-BEATS and Transformer. Darts provides a unified, scikit-learn-like API that makes it easy to switch between models and compare performance. It supports both univariate and multivariate forecasting, as well as probabilistic predictions.',
                architecture: 'Multi-Model Library Framework',
                year: '2021',
                developer: 'Unit8 AI',
                keyFeatures: ['Unified API', '20+ forecasting models', 'Probabilistic forecasting', 'Backtesting utilities', 'Pipeline support'],
                useCases: ['Research and development', 'Model comparison', 'Production systems', 'Educational purposes']
            },
            'NeuralForecast': {
                shortDesc: 'A collection of neural forecasting models optimized for speed and accuracy.',
                fullDesc: 'NeuralForecast is a Python library that provides state-of-the-art neural forecasting models with GPU acceleration. It includes implementations of cutting-edge deep learning architectures like NHITS, NBEATS, TFT (Temporal Fusion Transformer), and others. The library is optimized for performance and can handle large-scale forecasting tasks across thousands of time series.',
                architecture: 'Multi-Model Deep Learning Framework',
                year: '2022',
                developer: 'Nixtla',
                keyFeatures: ['GPU acceleration', 'Scalable to 1M+ series', 'State-of-the-art models', 'Automatic hyperparameter selection', 'Production-ready'],
                useCases: ['Large-scale forecasting', 'Real-time predictions', 'GPU-accelerated tasks', 'Industrial applications']
            },
            'Tempo': {
                shortDesc: 'A time series foundation model designed for general-purpose forecasting tasks.',
                fullDesc: 'TEMPO (Time series Exogenous model for Probabilistic fOrecasting) is a foundation model pre-trained on a large corpus of time series data. It uses a transformer architecture with specialized temporal encodings and can incorporate exogenous variables. The model is designed to work across multiple domains and can be fine-tuned for specific applications.',
                architecture: 'Transformer Foundation Model',
                year: '2024',
                developer: 'Salesforce Research',
                keyFeatures: ['Foundation model approach', 'Exogenous variable support', 'Multi-domain pre-training', 'Fine-tuning capability', 'Probabilistic outputs'],
                useCases: ['General forecasting', 'Transfer learning', 'Limited data scenarios', 'Multi-variate forecasting']
            },
            'Merlion': {
                shortDesc: 'Salesforce\'s Python library for time series intelligence with forecasting and anomaly detection.',
                fullDesc: 'Merlion is an end-to-end machine learning framework for time series that provides forecasting and anomaly detection capabilities. It includes implementations of various state-of-the-art models and provides a unified interface for training, evaluation, and deployment. Merlion emphasizes ease of use, modularity, and extensibility.',
                architecture: 'Multi-Model ML Framework',
                year: '2021',
                developer: 'Salesforce Research',
                keyFeatures: ['Forecasting and anomaly detection', 'Model ensembling', 'AutoML capabilities', 'Benchmark datasets', 'Production deployment tools'],
                useCases: ['Anomaly detection', 'Forecasting', 'Real-time monitoring', 'System health checks']
            },
            'Aeon': {
                shortDesc: 'A toolkit for learning from time series data with classification, regression, and clustering capabilities.',
                fullDesc: 'Aeon is a unified toolkit for machine learning with time series, providing a comprehensive suite of algorithms for time series classification, regression, clustering, and transformation. It is built on scikit-learn design principles and offers a wide range of classic and contemporary algorithms with a consistent API.',
                architecture: 'Scikit-learn Compatible Toolkit',
                year: '2023',
                developer: 'Aeon Development Team',
                keyFeatures: ['Classification algorithms', 'Regression methods', 'Clustering techniques', 'Feature extraction', 'Scikit-learn compatible'],
                useCases: ['Time series classification', 'Pattern recognition', 'Clustering analysis', 'Research applications']
            },
            'UCR': {
                shortDesc: 'UCR Time Series Classification Archive - a standard benchmark for time series classification.',
                fullDesc: 'The UCR Time Series Classification Archive is the most widely used benchmark for time series classification algorithms. It contains 128+ datasets from diverse domains including ECG, motion capture, sensor readings, and more. The archive provides standardized train/test splits and is used by researchers worldwide to evaluate classification algorithms.',
                architecture: 'Benchmark Dataset Collection',
                year: '2002 (continuously updated)',
                developer: 'UC Riverside',
                keyFeatures: ['128+ datasets', 'Standardized splits', 'Diverse domains', 'Classification benchmarks', 'Research standard'],
                useCases: ['Algorithm benchmarking', 'Research validation', 'Model comparison', 'Classification tasks']
            },
            'UEA': {
                shortDesc: 'UEA Time Series Classification Archive - multivariate time series classification benchmarks.',
                fullDesc: 'The UEA Multivariate Time Series Classification Archive extends UCR with datasets containing multiple synchronized time series. These datasets are crucial for evaluating algorithms that can leverage relationships between multiple variables. The archive includes datasets from various domains like human activity recognition, EEG analysis, and industrial processes.',
                architecture: 'Multivariate Benchmark Collection',
                year: '2018',
                developer: 'University of East Anglia',
                keyFeatures: ['Multivariate datasets', '30+ problems', 'Standardized evaluation', 'Cross-variable dependencies', 'Real-world applications'],
                useCases: ['Multivariate classification', 'Multi-sensor fusion', 'Activity recognition', 'Healthcare applications']
            },
            'TSLib': {
                shortDesc: 'A comprehensive library for deep learning-based time series analysis.',
                fullDesc: 'TSLib (Time Series Library) is a comprehensive deep learning library that implements numerous state-of-the-art models for time series forecasting, classification, and anomaly detection. It provides standardized implementations with consistent APIs, making it easy to compare different approaches and reproduce research results.',
                architecture: 'Deep Learning Model Collection',
                year: '2023',
                developer: 'Research Community',
                keyFeatures: ['50+ model implementations', 'Standardized benchmarks', 'Reproducible results', 'Modular design', 'Research-oriented'],
                useCases: ['Research and development', 'Model comparison', 'Algorithm benchmarking', 'Educational purposes']
            },
            'TimesNet': {
                shortDesc: 'A general time series analysis model that can handle forecasting, classification, and anomaly detection.',
                fullDesc: 'TimesNet is a unified architecture for multiple time series tasks. It introduces the concept of converting 1D time series into 2D tensors to capture multi-periodicity patterns. This transformation allows the model to use 2D kernels to extract complex temporal patterns. TimesNet achieves state-of-the-art performance across five major time series analysis tasks: forecasting, classification, anomaly detection, and imputation.',
                architecture: '2D Temporal Convolution Network',
                year: '2023',
                developer: 'Tsinghua University',
                keyFeatures: ['Multi-task capability', '2D temporal modeling', 'Multi-periodicity capture', 'Parameter efficiency', 'Task-agnostic design'],
                useCases: ['Forecasting', 'Classification', 'Anomaly detection', 'General time series analysis']
            },
            'TimesFM': {
                shortDesc: 'Google\'s Time Series Foundation Model pre-trained on large-scale time series data.',
                fullDesc: 'TimesFM (Time Series Foundation Model) is Google Research\'s decoder-only foundation model for time-series forecasting. Pre-trained on a massive corpus of 100 billion real-world time points, it demonstrates strong zero-shot forecasting capabilities across various domains and frequencies. The model uses patching and channel-independence to handle diverse time series characteristics.',
                architecture: 'Decoder-only Transformer',
                year: '2024',
                developer: 'Google Research',
                keyFeatures: ['100B data points pre-training', 'Zero-shot forecasting', 'Frequency-agnostic', 'Patch-based input', 'Open-source model'],
                useCases: ['Zero-shot forecasting', 'Quick deployment', 'Cross-domain applications', 'Research baseline']
            },
            'Timer-XL': {
                shortDesc: 'An extra-large time series model designed for comprehensive temporal pattern recognition.',
                fullDesc: 'Timer-XL is a large-scale foundation model for time series that leverages massive model capacity to capture intricate temporal patterns. Built on transformer architecture with billions of parameters, it can understand complex seasonality, trends, and irregular patterns across diverse time series domains.',
                architecture: 'Large-scale Transformer',
                year: '2024',
                developer: 'Research Community',
                keyFeatures: ['Billion-scale parameters', 'Cross-domain learning', 'Complex pattern recognition', 'Foundation model approach', 'Transfer learning'],
                useCases: ['Complex forecasting', 'Pattern discovery', 'Transfer learning', 'Research applications']
            },
            'TSMamba-ZS': {
                shortDesc: 'A zero-shot time series model based on the Mamba architecture.',
                fullDesc: 'TSMamba-ZS applies the Mamba state space model architecture to time series forecasting with zero-shot capabilities. Mamba offers an efficient alternative to transformers with linear time complexity while maintaining long-range dependency modeling. The zero-shot variant is pre-trained on diverse datasets for immediate deployment without fine-tuning.',
                architecture: 'State Space Model (Mamba)',
                year: '2024',
                developer: 'Research Community',
                keyFeatures: ['Linear complexity', 'Long-range dependencies', 'Zero-shot inference', 'Efficient computation', 'State space modeling'],
                useCases: ['Efficient long-sequence forecasting', 'Resource-constrained deployment', 'Quick adaptation', 'Real-time systems']
            },
            'AutoTimes': {
                shortDesc: 'Automated time series forecasting system with neural architecture search.',
                fullDesc: 'AutoTimes leverages neural architecture search (NAS) to automatically design optimal forecasting models for specific datasets. It explores the architecture space including components like attention mechanisms, convolutional layers, and recurrent units to find the best configuration. This approach eliminates manual architecture design and achieves superior performance through automated optimization.',
                architecture: 'Neural Architecture Search Framework',
                year: '2024',
                developer: 'Research Community',
                keyFeatures: ['Automated architecture design', 'Neural architecture search', 'Task-specific optimization', 'Performance maximization', 'No manual tuning'],
                useCases: ['Automated model design', 'Custom architectures', 'Performance optimization', 'Research and production']
            },
            'Monash TSER': {
                shortDesc: 'Monash Time Series Extrinsic Regression Archive for benchmark testing.',
                fullDesc: 'The Monash TSER Archive provides standardized datasets for time series extrinsic regression (TSER), where the goal is to predict a continuous target variable from time series data. This complements classification archives and is essential for evaluating regression algorithms on temporal data.',
                architecture: 'Benchmark Dataset Collection',
                year: '2021',
                developer: 'Monash University',
                keyFeatures: ['Regression benchmarks', 'Diverse domains', 'Standardized evaluation', 'Real-world problems', 'Research standard'],
                useCases: ['Regression algorithm testing', 'Model comparison', 'Research validation', 'Performance benchmarking']
            },
            'UTSD': {
                shortDesc: 'Universal Time Series Dataset for comprehensive model evaluation.',
                fullDesc: 'UTSD (Universal Time Series Dataset) is a large-scale collection designed to facilitate comprehensive evaluation of time series models across multiple domains and tasks. It includes data from various frequencies, lengths, and characteristics to test model robustness and generalization capabilities.',
                architecture: 'Multi-Domain Dataset Collection',
                year: '2023',
                developer: 'Research Community',
                keyFeatures: ['Multi-domain coverage', 'Various frequencies', 'Diverse characteristics', 'Comprehensive evaluation', 'Standardized benchmarks'],
                useCases: ['Model evaluation', 'Cross-domain testing', 'Generalization assessment', 'Research benchmarking']
            },
            'LPTM-Eval': {
                shortDesc: 'Large Pre-trained Time series Model evaluation benchmark.',
                fullDesc: 'LPTM-Eval is specifically designed to evaluate large pre-trained time series models. It includes challenging datasets and metrics that assess zero-shot performance, transfer learning capabilities, and generalization across diverse temporal patterns. This benchmark is crucial for comparing foundation models in the time series domain.',
                architecture: 'Foundation Model Benchmark Suite',
                year: '2024',
                developer: 'Research Community',
                keyFeatures: ['Foundation model evaluation', 'Zero-shot testing', 'Transfer learning metrics', 'Cross-domain assessment', 'Standardized protocols'],
                useCases: ['Foundation model testing', 'Pre-training evaluation', 'Model comparison', 'Research validation']
            }
        };

        const modelData = descriptions[modelName];
        if (!modelData) {
            return {
                shortDesc: 'A time series forecasting and analysis model used for evaluating datasets in this collection.',
                fullDesc: 'This model is part of the time series commons evaluation framework and is used to assess dataset performance across various forecasting and analysis tasks.',
                architecture: 'Various',
                year: 'N/A',
                developer: 'Research Community',
                keyFeatures: ['Time series analysis', 'Dataset evaluation'],
                useCases: ['Benchmarking', 'Model evaluation']
            };
        }
        
        return modelData;
    }

    openModelInfoModal(modelName) {
        const modal = document.getElementById('model-info-modal');
        const modalBody = document.getElementById('model-info-body');
        const modalTitle = document.getElementById('model-info-title');

        if (!modal || !modalBody || !modalTitle) return;

        const modelInfo = this.getModelInfo(modelName);
        
        modalTitle.textContent = modelInfo.name;

        // Create comprehensive model info content
        modalBody.innerHTML = `
            <div class="modal-section model-overview">
                <div class="model-meta-info">
                    <div class="meta-item">
                        <span class="meta-label">Architecture:</span>
                        <span class="meta-value">${this.escapeHtml(modelInfo.architecture)}</span>
                    </div>
                    <div class="meta-item">
                        <span class="meta-label">Year:</span>
                        <span class="meta-value">${this.escapeHtml(modelInfo.year)}</span>
                    </div>
                    <div class="meta-item">
                        <span class="meta-label">Developer:</span>
                        <span class="meta-value">${this.escapeHtml(modelInfo.developer)}</span>
                    </div>
                </div>
            </div>

            <div class="modal-section">
                <h3>Overview</h3>
                <p class="model-description-text">${this.escapeHtml(modelInfo.fullDesc)}</p>
            </div>

            <div class="modal-section">
                <h3>Key Features</h3>
                <ul class="model-features-list">
                    ${modelInfo.keyFeatures.map(feature => `
                        <li>${this.escapeHtml(feature)}</li>
                    `).join('')}
                </ul>
            </div>

            <div class="modal-section">
                <h3>Common Use Cases</h3>
                <div class="use-cases-grid">
                    ${modelInfo.useCases.map(useCase => `
                        <div class="use-case-tag">${this.escapeHtml(useCase)}</div>
                    `).join('')}
                </div>
            </div>

            <div class="modal-section">
                <h3>Evaluation Coverage</h3>
                <div class="model-stats-grid">
                    <div class="model-stat-card">
                        <div class="stat-number">${modelInfo.datasetCount}</div>
                        <div class="stat-label">Datasets Evaluated</div>
                    </div>
                    <div class="model-stat-card">
                        <div class="stat-number">${Math.round((modelInfo.datasetCount / this.allModels.length) * 100)}%</div>
                        <div class="stat-label">Coverage</div>
                    </div>
                </div>
            </div>

            <div class="modal-section">
                <h3>Sample Datasets</h3>
                <div class="sample-datasets-list">
                    ${modelInfo.datasets.slice(0, 5).map(dataset => `
                        <div class="sample-dataset-item">
                            <strong>${this.escapeHtml(dataset.name)}</strong>
                            <span class="dataset-domain-tag">${this.escapeHtml((dataset.domain || '').split(',')[0].trim())}</span>
                        </div>
                    `).join('')}
                    ${modelInfo.datasetCount > 5 ? `<p class="more-datasets">... and ${modelInfo.datasetCount - 5} more datasets</p>` : ''}
                </div>
            </div>

            <div class="modal-section model-actions">
                <button class="filter-by-model-btn" id="filter-by-model-btn">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"></polygon>
                    </svg>
                    Show All Datasets Evaluated by ${this.escapeHtml(modelInfo.name)}
                </button>
            </div>
        `;

        // Add click handler to filter button
        const filterBtn = modalBody.querySelector('#filter-by-model-btn');
        if (filterBtn) {
            filterBtn.addEventListener('click', () => {
                // Close both modals
                this.closeModal();
                this.closeModelInfoModal();
                
                // Activate the model filter
                const checkbox = document.getElementById(`model-${modelName}`);
                if (checkbox && !checkbox.checked) {
                    checkbox.checked = true;
                    this.filters.benchmarks.add(modelName);
                    const filterItem = checkbox.closest('.model-filter-item');
                    if (filterItem) {
                        filterItem.classList.add('active');
                    }
                    
                    // Apply filters and update display
                    this.applyFilters();
                    this.renderModels();
                    
                    // Scroll to the filter in sidebar
                    setTimeout(() => {
                        if (checkbox) {
                            checkbox.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        }
                    }, 100);
                }
            });
        }

        // Show modal with animation
        modal.classList.add('active');
    }

    closeModelInfoModal() {
        const modal = document.getElementById('model-info-modal');
        if (modal) {
            modal.classList.remove('active');
        }
    }

    escapeHtml(text) {
        if (!text) return '';
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return text.toString().replace(/[&<>"']/g, m => map[m]);
    }

    showError(message) {
        const grid = document.getElementById('models-grid');
        if (grid) {
            grid.innerHTML = `
                <div class="no-results">
                    <div class="no-results-icon">⚠️</div>
                    <h3>Error</h3>
                    <p>${message}</p>
                </div>
            `;
        }
    }
}

// Initialize the catalog when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new ModelsCatalog();
});
