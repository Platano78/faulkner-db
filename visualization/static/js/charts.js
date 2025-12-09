class DashboardRenderer {
    constructor() {
        this.stats = {};
        this.graphData = {};
        this.startTime = Date.now();
    }

    async init() {
        await this.fetchData();
        this.renderStats();
        this.renderCharts();
        this.logLoadTime();
    }

    async fetchData() {
        try {
            const [statsRes, graphRes] = await Promise.all([
                fetch('/api/stats'),
                fetch('/api/graph/full')
            ]);
            this.stats = await statsRes.json();
            this.graphData = await graphRes.json();
        } catch (error) {
            console.error('Failed to fetch dashboard data:', error);
        }
    }

    renderStats() {
        const totalStats = document.getElementById('total-stats');
        const decisions = this.graphData.nodes?.filter(n => n.type === 'Decision').length || 0;
        const patterns = this.graphData.nodes?.filter(n => n.type === 'Pattern').length || 0;
        const failures = this.graphData.nodes?.filter(n => n.type === 'Failure').length || 0;
        
        totalStats.innerHTML = `
            <div class="stat-card">
                <h3>Total Decisions</h3>
                <p class="stat-value">${decisions}</p>
            </div>
            <div class="stat-card">
                <h3>Patterns</h3>
                <p class="stat-value">${patterns}</p>
            </div>
            <div class="stat-card">
                <h3>Failures</h3>
                <p class="stat-value">${failures}</p>
            </div>
        `;

        const projectStats = document.getElementById('project-stats');
        projectStats.innerHTML = `
            <div class="stat-card">
                <h3>Total Nodes</h3>
                <p class="stat-value">${this.stats.node_count || 0}</p>
            </div>
            <div class="stat-card">
                <h3>Total Edges</h3>
                <p class="stat-value">${this.stats.edge_count || 0}</p>
            </div>
            <div class="stat-card">
                <h3>Graph Density</h3>
                <p class="stat-value">${(this.stats.density || 0).toFixed(3)}</p>
            </div>
        `;
    }

    renderCharts() {
        // Simple placeholder charts
        const timeCtx = document.getElementById('decisions-over-time')?.getContext('2d');
        if (timeCtx) {
            new Chart(timeCtx, {
                type: 'line',
                data: {
                    labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
                    datasets: [{
                        label: 'Decisions',
                        data: [0, 0, 0, 0, 0, this.stats.node_count || 0],
                        borderColor: '#3b82f6',
                        backgroundColor: 'rgba(59, 130, 246, 0.1)',
                        tension: 0.4
                    }]
                },
                options: {
                    responsive: true,
                    plugins: { legend: { labels: { color: '#e5e7eb' } } },
                    scales: {
                        x: { ticks: { color: '#aaa' }, grid: { color: '#333' } },
                        y: { ticks: { color: '#aaa' }, grid: { color: '#333' } }
                    }
                }
            });
        }

        const categoryCtx = document.getElementById('decisions-by-category')?.getContext('2d');
        if (categoryCtx) {
            const decisions = this.graphData.nodes?.filter(n => n.type === 'Decision').length || 0;
            const patterns = this.graphData.nodes?.filter(n => n.type === 'Pattern').length || 0;
            const failures = this.graphData.nodes?.filter(n => n.type === 'Failure').length || 0;
            
            new Chart(categoryCtx, {
                type: 'bar',
                data: {
                    labels: ['Decisions', 'Patterns', 'Failures'],
                    datasets: [{
                        data: [decisions, patterns, failures],
                        backgroundColor: ['#3b82f6', '#10b981', '#ef4444']
                    }]
                },
                options: {
                    responsive: true,
                    plugins: { legend: { display: false } },
                    scales: {
                        x: { ticks: { color: '#aaa' }, grid: { color: '#333' } },
                        y: { ticks: { color: '#aaa' }, grid: { color: '#333' } }
                    }
                }
            });
        }

        const projectCtx = document.getElementById('project-distribution')?.getContext('2d');
        if (projectCtx) {
            new Chart(projectCtx, {
                type: 'pie',
                data: {
                    labels: ['Current Data'],
                    datasets: [{
                        data: [this.stats.node_count || 1],
                        backgroundColor: ['#3b82f6']
                    }]
                },
                options: {
                    responsive: true,
                    plugins: { legend: { labels: { color: '#e5e7eb' } } }
                }
            });
        }
    }

    logLoadTime() {
        const loadTime = Date.now() - this.startTime;
        console.log(`Dashboard loaded in ${loadTime}ms`);
        if (loadTime > 1000) {
            console.warn('Dashboard load time exceeds 1s target');
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const dashboard = new DashboardRenderer();
    dashboard.init();
});
