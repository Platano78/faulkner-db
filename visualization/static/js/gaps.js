class GapDetector {
    constructor() {
        this.gaps = [];
        this.fixedGaps = new Set();
    }

    async fetchGaps() {
        try {
            const response = await fetch('/api/gaps');
            const data = await response.json();
            this.gaps = data.nodes || [];
            this.renderHeatmap();
        } catch (error) {
            console.error('Failed to fetch gaps:', error);
            document.getElementById('heatmap-container').innerHTML = 
                '<p style="color: #ef4444;">Error loading gaps data</p>';
        }
    }

    renderHeatmap() {
        const container = document.getElementById('heatmap-container');
        
        if (this.gaps.length === 0) {
            container.innerHTML = '<p style="color: #e5e7eb;">No isolated nodes found. Knowledge graph is well connected!</p>';
            return;
        }
        
        container.innerHTML = '<h2>Isolated Nodes (No Connections)</h2>';
        
        this.gaps.forEach(gap => {
            if (this.fixedGaps.has(gap.id)) return;
            
            const gapElement = document.createElement('div');
            gapElement.className = 'gap-item';
            gapElement.style.backgroundColor = '#ef4444';
            gapElement.innerHTML = `
                <div class="gap-info">
                    <span class="severity">HIGH</span>
                    <span class="nodes">${gap.title || gap.id}</span>
                </div>
            `;
            
            gapElement.addEventListener('click', () => this.showGapDetails(gap));
            container.appendChild(gapElement);
        });
    }

    showGapDetails(gap) {
        const details = document.getElementById('gap-details');
        details.innerHTML = `
            <h3>Gap Details</h3>
            <p><strong>Node:</strong> ${gap.title || gap.id}</p>
            <p><strong>Type:</strong> ${gap.type || 'Unknown'}</p>
            <p><strong>Issue:</strong> This node has no connections to other nodes</p>
            <button onclick="gapDetector.markAsFixed('${gap.id}')">Mark as Fixed</button>
        `;
    }

    markAsFixed(gapId) {
        this.fixedGaps.add(gapId);
        this.renderHeatmap();
        document.getElementById('gap-details').innerHTML = '<p style="color: #10b981;">Gap marked as fixed!</p>';
    }
}

const gapDetector = new GapDetector();

document.addEventListener('DOMContentLoaded', () => {
    gapDetector.fetchGaps();
    
    const addButton = document.getElementById('add-relationship');
    if (addButton) {
        addButton.addEventListener('click', () => {
            alert('Use MCP find_related tool to add relationships between nodes.');
        });
    }
});
