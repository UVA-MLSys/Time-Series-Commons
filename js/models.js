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
        
        if (this.currentView === 'grid') {
            this.renderCards(filtered, 'all-datasets-grid', 'dataset');
            document.getElementById('all-datasets-list').classList.remove('active');
        } else {
            this.renderList(filtered, 'all-datasets-list', 'dataset');
            document.getElementById('all-datasets-list').classList.add('active');
        }
    }

    renderAllModels() {
        const filtered = this.getFilteredAndSorted(this.models);
        document.getElementById('models-count').textContent = `${filtered.length} models`;
        
        if (this.currentView === 'grid') {
            this.renderCards(filtered, 'all-models-grid', 'model');
            document.getElementById('all-models-list').classList.remove('active');
        } else {
            this.renderList(filtered, 'all-models-list', 'model');
            document.getElementById('all-models-list').classList.add('active');
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
    }

    createCard(item, type) {
        const isDataset = type === 'dataset';
        const bgClass = isDataset ? 'dataset-bg' : 'model-bg';
        const icon = isDataset ? '📊' : '🤖';
        
        const description = isDataset 
            ? this.truncateText(item.description || 'No description available', 80)
            : item.description || '';

        const domain = item.domain || 'General';

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
    }

    createListItem(item, type) {
        const isDataset = type === 'dataset';
        const icon = isDataset ? '📊' : '🤖';
        
        const meta = isDataset
            ? `${item.domain || 'General'} · ${item.timePoints || 'N/A'} points`
            : `${item.datasetsCount || 0} datasets`;

        return `
            <div class="list-item" data-id="${item.id}" data-type="${type}">
                <div class="list-icon">
                    <span style="font-size: 24px;">${icon}</span>
                </div>
                <div class="list-content">
                    <div class="list-title">${this.escapeHtml(item.name)}</div>
                    <div class="list-meta">${meta}</div>
                </div>
                ${isDataset ? `<span class="list-badge">${item.interval || 'N/A'}</span>` : ''}
            </div>
        `;
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
}

// Initialize the catalog when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    new NotebookCatalog();
});
