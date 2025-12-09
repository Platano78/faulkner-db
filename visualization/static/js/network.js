class NetworkGraph {
    constructor() {
        this.nodes = [];
        this.edges = [];
        this.simulation = null;
        this.svg = null;
        this.zoom = null;
        this.lastRenderTime = 0;
        this.frameCount = 0;
        this.lastTime = performance.now();
        this.fps = 60;
        
        this.init();
        this.startPerformanceMonitor();
    }

    async init() {
        const container = d3.select('#graph-container');
        const width = window.innerWidth - 300;
        const height = window.innerHeight;
        
        this.svg = container.append('svg')
            .attr('width', width)
            .attr('height', height);

        this.svg.append('defs').append('marker')
            .attr('id', 'arrowhead')
            .attr('viewBox', '0 -5 10 10')
            .attr('refX', 15)
            .attr('refY', 0)
            .attr('markerWidth', 6)
            .attr('markerHeight', 6)
            .attr('orient', 'auto')
            .append('path')
            .attr('d', 'M0,-5L10,0L0,5')
            .attr('fill', '#4b5563');

        this.g = this.svg.append('g');
        
        this.zoom = d3.zoom()
            .scaleExtent([0.1, 4])
            .on('zoom', (event) => {
                this.g.attr('transform', event.transform);
            });

        this.svg.call(this.zoom);

        await this.loadData();
    }

    async loadData() {
        try {
            const response = await fetch('/api/graph/full');
            const data = await response.json();
            this.nodes = data.nodes || [];
            this.edges = data.edges || [];
            
            if (this.nodes.length === 0) {
                this.showEmptyState();
            } else {
                this.createSimulation();
            }
        } catch (error) {
            console.error('Failed to load graph data:', error);
            this.showErrorState(error);
        }
    }

    showEmptyState() {
        this.g.append('text')
            .attr('x', (window.innerWidth - 300) / 2)
            .attr('y', window.innerHeight / 2)
            .attr('text-anchor', 'middle')
            .attr('fill', '#e5e7eb')
            .attr('font-size', '20px')
            .text('No decisions in database. Add decisions via MCP tools.');
    }

    showErrorState(error) {
        this.g.append('text')
            .attr('x', (window.innerWidth - 300) / 2)
            .attr('y', window.innerHeight / 2)
            .attr('text-anchor', 'middle')
            .attr('fill', '#ef4444')
            .attr('font-size', '16px')
            .text('Error loading graph: ' + error.message);
    }

    createSimulation() {
        const width = window.innerWidth - 300;
        const height = window.innerHeight;
        
        this.nodes.forEach(node => {
            node.radius = 10;
        });

        this.simulation = d3.forceSimulation(this.nodes)
            .force('charge', d3.forceManyBody().strength(-200))
            .force('link', d3.forceLink(this.edges).id(d => d.id).distance(60))
            .force('center', d3.forceCenter(width / 2, height / 2))
            .force('collision', d3.forceCollide().radius(d => d.radius + 5));

        this.renderGraph();
    }

    renderGraph() {
        const startTime = performance.now();

        const link = this.g.append('g')
            .selectAll('line')
            .data(this.edges)
            .enter().append('line')
            .attr('class', 'link')
            .attr('stroke', '#4b5563')
            .attr('stroke-width', 1.5)
            .attr('marker-end', 'url(#arrowhead)');

        const node = this.g.append('g')
            .selectAll('circle')
            .data(this.nodes)
            .enter().append('circle')
            .attr('class', 'node')
            .attr('r', d => d.radius)
            .attr('fill', d => this.getNodeColor(d.type))
            .attr('stroke', '#fff')
            .attr('stroke-width', 1.5)
            .style('cursor', 'pointer')
            .call(d3.drag()
                .on('start', (event, d) => {
                    if (!event.active) this.simulation.alphaTarget(0.3).restart();
                    d.fx = d.x;
                    d.fy = d.y;
                })
                .on('drag', (event, d) => {
                    d.fx = event.x;
                    d.fy = event.y;
                })
                .on('end', (event, d) => {
                    if (!event.active) this.simulation.alphaTarget(0);
                    d.fx = null;
                    d.fy = null;
                }))
            .on('click', (event, d) => showNodeDetails(d))
            .on('dblclick', (event, d) => this.centerNode(d));

        node.append('title')
            .text(d => `${d.title || d.id}\n${d.description || ''}`);

        this.simulation.on('tick', () => {
            link
                .attr('x1', d => d.source.x)
                .attr('y1', d => d.source.y)
                .attr('x2', d => d.target.x)
                .attr('y2', d => d.target.y);

            node
                .attr('cx', d => d.x)
                .attr('cy', d => d.y);
        });

        this.lastRenderTime = performance.now() - startTime;
    }

    getNodeColor(type) {
        const colors = {
            'Decision': '#3b82f6',
            'Pattern': '#10b981',
            'Failure': '#ef4444'
        };
        return colors[type] || '#6b7280';
    }

    centerNode(node) {
        const width = window.innerWidth - 300;
        const height = window.innerHeight;
        const transform = d3.zoomIdentity
            .translate(width / 2, height / 2)
            .scale(2)
            .translate(-node.x, -node.y);
        
        this.svg.transition()
            .duration(750)
            .call(this.zoom.transform, transform);
    }

    startPerformanceMonitor() {
        setInterval(() => {
            const now = performance.now();
            this.frameCount++;
            if (now >= this.lastTime + 1000) {
                this.fps = Math.round((this.frameCount * 1000) / (now - this.lastTime));
                this.frameCount = 0;
                this.lastTime = now;
                
                document.getElementById('fps-counter').textContent = `FPS: ${this.fps}`;
                document.getElementById('render-time').textContent = `Render: ${Math.round(this.lastRenderTime)}ms`;
            }
        }, 100);
    }
}

class WebSocketClient {
    constructor(networkGraph) {
        this.networkGraph = networkGraph;
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
        this.baseDelay = 1000;
        this.connect();
    }

    connect() {
        try {
            this.ws = new WebSocket('ws://localhost:8082/ws');
            
            this.ws.onopen = () => {
                console.log('WebSocket connected');
                this.reconnectAttempts = 0;
                this.updateConnectionStatus(true);
            };

            this.ws.onmessage = (event) => {
                const message = JSON.parse(event.data);
                this.handleMessage(message);
            };

            this.ws.onclose = () => {
                console.log('WebSocket disconnected');
                this.updateConnectionStatus(false);
                this.scheduleReconnect();
            };

            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.ws.close();
            };
        } catch (error) {
            console.error('Failed to create WebSocket:', error);
            this.scheduleReconnect();
        }
    }

    scheduleReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('Max reconnection attempts reached');
            return;
        }

        const delay = this.baseDelay * Math.pow(2, this.reconnectAttempts) + Math.floor(Math.random() * 1000);
        this.reconnectAttempts++;
        console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);
        
        setTimeout(() => this.connect(), delay);
    }

    handleMessage(message) {
        switch(message.type) {
            case 'decision_added':
                this.showToast(`New decision added: ${message.data.title}`);
                this.networkGraph.loadData();
                break;
            case 'decision_updated':
                this.showToast('Decision updated');
                this.networkGraph.loadData();
                break;
            case 'gap_detected':
                this.showToast('Gap detected in knowledge graph', 'warning');
                break;
        }
    }

    showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.textContent = message;
        document.getElementById('toast-container').appendChild(toast);
        
        setTimeout(() => toast.remove(), 3000);
    }

    updateConnectionStatus(connected) {
        const statusElement = document.getElementById('connection-status');
        if (statusElement) {
            statusElement.className = connected ? 'status-connected' : 'status-disconnected';
            statusElement.textContent = connected ? 'Connected' : 'Disconnected';
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const graph = new NetworkGraph();
    const wsClient = new WebSocketClient(graph);
    window.networkGraph = graph;
    window.wsClient = wsClient;
});
