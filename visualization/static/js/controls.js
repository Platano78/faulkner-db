document.addEventListener('DOMContentLoaded', () => {
    const chargeSlider = document.getElementById('charge-slider');
    const distanceSlider = document.getElementById('distance-slider');
    const resetButton = document.getElementById('reset-view');
    const searchBox = document.getElementById('search-box');

    if (chargeSlider) {
        chargeSlider.addEventListener('input', (e) => {
            if (window.networkGraph && window.networkGraph.simulation) {
                window.networkGraph.simulation.force('charge').strength(parseInt(e.target.value));
                window.networkGraph.simulation.alphaTarget(0.1).restart();
            }
        });
    }

    if (distanceSlider) {
        distanceSlider.addEventListener('input', (e) => {
            if (window.networkGraph && window.networkGraph.simulation) {
                window.networkGraph.simulation.force('link').distance(parseInt(e.target.value));
                window.networkGraph.simulation.alphaTarget(0.1).restart();
            }
        });
    }

    if (resetButton) {
        resetButton.addEventListener('click', () => {
            if (window.networkGraph && window.networkGraph.svg) {
                window.networkGraph.svg.transition()
                    .duration(750)
                    .call(window.networkGraph.zoom.transform, d3.zoomIdentity);
            }
        });
    }

    if (searchBox) {
        searchBox.addEventListener('input', async (e) => {
            const query = e.target.value;
            if (query.length > 2) {
                try {
                    const response = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
                    const data = await response.json();
                    // Highlight matching nodes
                    if (window.networkGraph) {
                        window.networkGraph.highlightNodes(data.nodes);
                    }
                } catch (error) {
                    console.error('Search failed:', error);
                }
            }
        });
    }
});
