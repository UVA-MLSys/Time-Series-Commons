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

        // Keyboard events
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.closeModal();
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

    renderModels() {
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
                // Close modal
                this.closeModal();
                
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
                    if (checkbox) {
                        checkbox.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    }
                }
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
