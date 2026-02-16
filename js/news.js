/**
 * News Section - Time Series Commons
 * Loads and displays recent news items from JSON data
 */

class NewsManager {
    constructor() {
        this.news = [];
        this.maxItems = 3; // Display only 3 most recent items
        this.container = null;
    }

    async init() {
        this.container = document.getElementById('news-container');
        if (!this.container) {
            console.warn('News container not found');
            return;
        }

        await this.loadNews();
        this.renderNews();
    }

    async loadNews() {
        try {
            const response = await fetch('./data/news.json');
            if (!response.ok) {
                throw new Error('Failed to load news data');
            }
            const data = await response.json();
            this.news = data.news || [];
            
            // Sort by date (most recent first)
            this.news.sort((a, b) => new Date(b.date) - new Date(a.date));
        } catch (error) {
            console.error('Error loading news:', error);
            this.container.innerHTML = '<p style="text-align: center; color: #7f8c8d;">No news available at the moment.</p>';
        }
    }

    renderNews() {
        if (this.news.length === 0) {
            this.container.innerHTML = '<p style="text-align: center; color: #7f8c8d;">No news available at the moment.</p>';
            return;
        }

        // Get only the most recent items
        const recentNews = this.news.slice(0, this.maxItems);
        
        // Clear container
        this.container.innerHTML = '';

        // Render each news item
        recentNews.forEach(item => {
            const card = this.createNewsCard(item);
            this.container.appendChild(card);
        });
    }

    createNewsCard(item) {
        const card = document.createElement('div');
        card.className = 'news-card';
        card.onclick = () => {
            if (item.link) {
                window.location.href = item.link;
            }
        };

        // Format date
        const formattedDate = this.formatDate(item.date);

        // Get badge label
        const badgeLabel = this.getBadgeLabel(item.type);

        // Handle image
        const imageStyle = item.image 
            ? `background-image: url('${item.image}');` 
            : 'background-color: #e8ecef;';

        card.innerHTML = `
            <div class="news-card-image" style="${imageStyle}">
                <div class="news-type-badge ${item.type}">${badgeLabel}</div>
            </div>
            <div class="news-card-content">
                <div class="news-card-date">${formattedDate}</div>
                <div class="news-card-title">${this.escapeHtml(item.title)}</div>
                <div class="news-card-description">${this.escapeHtml(item.description)}</div>
            </div>
        `;

        return card;
    }

    formatDate(dateString) {
        const date = new Date(dateString);
        const options = { year: 'numeric', month: 'short', day: 'numeric' };
        return date.toLocaleDateString('en-US', options);
    }

    getBadgeLabel(type) {
        const labels = {
            'paper': 'Paper',
            'release': 'Release',
            'talk': 'Talk',
            'award': 'Award'
        };
        return labels[type] || 'News';
    }

    escapeHtml(text) {
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return text.replace(/[&<>"']/g, m => map[m]);
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    const newsManager = new NewsManager();
    newsManager.init();
});
