class Timeline {
    constructor(container) {
        this.container = container;
        this.margin = { top: 40, right: 20, bottom: 60, left: 120 };
        this.width = window.innerWidth - this.margin.left - this.margin.right;
        this.height = window.innerHeight - this.margin.top - this.margin.bottom - 100;
        this.data = null;
        this.filteredData = null;
        this.projects = [];
        this.xScale = null;
        this.yScale = null;
    }

    async fetchData() {
        const response = await fetch('/api/timeline');
        this.data = await response.json();
        this.projects = [...new Set(this.data.nodes.map(d => d.project || 'Uncategorized'))];
        this.filteredData = {...this.data};
    }

    initScales() {
        const dates = this.filteredData.nodes.map(d => new Date(d.timestamp)).filter(d => !isNaN(d));
        this.xScale = d3.scaleTime()
            .domain(d3.extent(dates))
            .range([0, this.width]);

        this.yScale = d3.scalePoint()
            .domain(this.projects)
            .range([0, this.height])
            .padding(0.5);
    }

    createSVG() {
        d3.select(this.container).select('svg').remove();
        this.svg = d3.select(this.container)
            .append('svg')
            .attr('width', this.width + this.margin.left + this.margin.right)
            .attr('height', this.height + this.margin.top + this.margin.bottom);

        this.g = this.svg.append('g')
            .attr('transform', `translate(${this.margin.left},${this.margin.top})`);
    }

    drawAxes() {
        const xAxis = d3.axisBottom(this.xScale);
        const yAxis = d3.axisLeft(this.yScale);

        this.g.append('g')
            .attr('class', 'x axis')
            .attr('transform', `translate(0,${this.height})`)
            .call(xAxis)
            .selectAll('text')
            .attr('fill', '#aaa');

        this.g.append('g')
            .attr('class', 'y axis')
            .call(yAxis)
            .selectAll('text')
            .attr('fill', '#aaa');
    }

    drawNodes() {
        this.nodeGroup = this.g.selectAll('.node')
            .data(this.filteredData.nodes.filter(d => d.timestamp))
            .enter().append('circle')
            .attr('class', 'node')
            .attr('cx', d => this.xScale(new Date(d.timestamp)))
            .attr('cy', d => this.yScale(d.project || 'Uncategorized'))
            .attr('r', 8)
            .attr('fill', '#3b82f6')
            .attr('stroke', '#fff')
            .attr('stroke-width', 2)
            .style('cursor', 'pointer')
            .on('click', (event, d) => window.open(`/static/index.html?highlight=${d.id}`, '_blank'));

        this.nodeGroup.append('title')
            .text(d => `${d.title || d.id}\n${d.project || 'Uncategorized'}`);
    }

    async init() {
        const start = performance.now();
        await this.fetchData();
        if (this.filteredData.nodes.length === 0) {
            d3.select(this.container).append('p')
                .style('color', '#e5e7eb')
                .style('text-align', 'center')
                .style('margin-top', '100px')
                .text('No timeline data available. Add decisions with timestamps.');
            return;
        }
        this.initScales();
        this.createSVG();
        this.drawAxes();
        this.drawNodes();
        console.log(`Timeline rendered in ${performance.now() - start}ms`);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const timeline = new Timeline('#timeline-container');
    timeline.init();
    window.timeline = timeline;
});
