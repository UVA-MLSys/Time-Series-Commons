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
        this.currentSort = 'recent';
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

        // Create model objects with counts
        this.models = Array.from(modelsSet).map(modelName => {
            const datasetsCount = this.allData.filter(d => 
                d.benchmarks && d.benchmarks[modelName]
            ).length;
            
            return {
                id: modelName.toLowerCase().replace(/\s+/g, '-'),
                name: modelName,
                type: 'model',
                datasetsCount: datasetsCount,
                description: `Evaluated on ${datasetsCount} dataset${datasetsCount !== 1 ? 's' : ''}`
            };
        });
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
        // Render featured datasets (first 6)
        const featuredDatasets = this.getFilteredAndSorted(this.datasets).slice(0, 6);
        this.renderCards(featuredDatasets, 'featured-datasets-grid', 'dataset');

        // Render featured models (first 6)
        const featuredModels = this.getFilteredAndSorted(this.models).slice(0, 6);
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
                case 'name':
                    return a.name.localeCompare(b.name);
                case 'domain':
                    return (a.domain || '').localeCompare(b.domain || '');
                case 'recent':
                default:
                    return 0; // Keep original order
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
                        return `<div class="benchmark-badge ${isEvaluated ? '' : 'inactive'}">${this.escapeHtml(modelName)}</div>`;
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
