async function showNodeDetails(node) {
    const panel = document.getElementById('details-panel');
    const details = document.getElementById('node-details');

    // Show loading state
    details.innerHTML = `<div class="loading">Loading ${node.id}...</div>`;
    panel.classList.remove('hidden');

    // Fetch fresh data for this node
    let fullNode = node;
    try {
        const response = await fetch(`/api/node/${encodeURIComponent(node.id)}`);
        const data = await response.json();
        if (data.node) {
            fullNode = data.node;
        }
    } catch (e) {
        console.warn('Could not fetch fresh node data:', e);
    }

    renderNodeDetails(fullNode, details);
}

function renderNodeDetails(node, container) {
    // Helper to truncate long text with expand option
    function formatText(text, maxLength = 500) {
        if (!text) return '<span class="empty">(empty)</span>';
        text = String(text);
        const escaped = escapeHtml(text);
        if (text.length <= maxLength) return escaped;
        const truncated = escapeHtml(text.substring(0, maxLength));
        return `<span class="truncated">${truncated}...</span>
                <button class="expand-btn" onclick="expandText(this, '${btoa(unescape(encodeURIComponent(text)))}')">Show more</button>`;
    }

    function escapeHtml(text) {
        if (!text) return '';
        return String(text)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/\n/g, '<br>');
    }

    function parseJsonArray(text) {
        if (!text) return [];
        if (Array.isArray(text)) return text;
        try {
            const arr = JSON.parse(text);
            return Array.isArray(arr) ? arr : [];
        } catch {
            return [];
        }
    }

    // Build content based on node type
    let content = `
        <div class="node-header ${(node.type || 'unknown').toLowerCase()}">
            <span class="node-type-badge">${node.type || 'Unknown'}</span>
            <h3>${escapeHtml(node.name || node.title || node.id)}</h3>
        </div>
        <div class="node-meta">
            <p><strong>ID:</strong> <code>${node.id}</code></p>
            ${node.timestamp ? `<p><strong>Date:</strong> ${new Date(node.timestamp).toLocaleDateString()} ${new Date(node.timestamp).toLocaleTimeString()}</p>` : ''}
        </div>
    `;

    // Type-specific content
    if (node.type === 'Pattern') {
        if (node.context) {
            content += `
                <div class="node-section">
                    <h4>Context</h4>
                    <p>${formatText(node.context, 400)}</p>
                </div>
            `;
        }
        if (node.implementation) {
            content += `
                <div class="node-section">
                    <h4>Implementation</h4>
                    <pre class="code-block">${formatText(node.implementation, 1000)}</pre>
                </div>
            `;
        }
        const useCases = parseJsonArray(node.use_cases);
        if (useCases.length > 0) {
            content += `
                <div class="node-section">
                    <h4>Use Cases</h4>
                    <ul>${useCases.map(uc => `<li>${escapeHtml(uc)}</li>`).join('')}</ul>
                </div>
            `;
        }
    } else if (node.type === 'Decision') {
        if (node.description) {
            content += `
                <div class="node-section">
                    <h4>Description</h4>
                    <p>${formatText(node.description, 500)}</p>
                </div>
            `;
        }
        if (node.rationale) {
            content += `
                <div class="node-section">
                    <h4>Rationale</h4>
                    <p>${formatText(node.rationale, 800)}</p>
                </div>
            `;
        }
        const alternatives = parseJsonArray(node.alternatives);
        if (alternatives.length > 0) {
            content += `
                <div class="node-section">
                    <h4>Alternatives Considered</h4>
                    <ul>${alternatives.map(alt => `<li>${escapeHtml(alt)}</li>`).join('')}</ul>
                </div>
            `;
        }
        const relatedTo = parseJsonArray(node.related_to);
        if (relatedTo.length > 0) {
            content += `
                <div class="node-section">
                    <h4>Related To</h4>
                    <ul>${relatedTo.map(r => `<li><code>${escapeHtml(r)}</code></li>`).join('')}</ul>
                </div>
            `;
        }
    } else if (node.type === 'Failure') {
        if (node.attempt) {
            content += `
                <div class="node-section">
                    <h4>What Was Attempted</h4>
                    <p>${formatText(node.attempt, 500)}</p>
                </div>
            `;
        }
        if (node.reason_failed) {
            content += `
                <div class="node-section">
                    <h4>Why It Failed</h4>
                    <p>${formatText(node.reason_failed, 500)}</p>
                </div>
            `;
        }
        if (node.lesson_learned) {
            content += `
                <div class="node-section">
                    <h4>Lesson Learned</h4>
                    <p>${formatText(node.lesson_learned, 500)}</p>
                </div>
            `;
        }
        if (node.alternative_solution) {
            content += `
                <div class="node-section">
                    <h4>Alternative Solution</h4>
                    <p>${formatText(node.alternative_solution, 500)}</p>
                </div>
            `;
        }
    }

    // Show any other fields not explicitly handled
    const knownFields = ['id', 'type', 'timestamp', 'name', 'title', 'context', 'implementation',
                         'use_cases', 'description', 'rationale', 'alternatives', 'related_to',
                         'attempt', 'reason_failed', 'lesson_learned', 'alternative_solution', 'source_files'];
    const extraFields = Object.entries(node).filter(([k, v]) => !knownFields.includes(k) && v);

    if (extraFields.length > 0) {
        content += `<div class="node-section"><h4>Additional Info</h4>`;
        for (const [key, value] of extraFields) {
            content += `<p><strong>${escapeHtml(key)}:</strong> ${formatText(String(value), 200)}</p>`;
        }
        content += `</div>`;
    }

    container.innerHTML = content;
}

// Global function to expand truncated text
function expandText(btn, encodedText) {
    try {
        const text = decodeURIComponent(escape(atob(encodedText)));
        const span = btn.previousElementSibling;
        span.innerHTML = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\n/g, '<br>');
        span.classList.remove('truncated');
        btn.remove();
    } catch (e) {
        console.error('Failed to expand text:', e);
    }
}

document.addEventListener('click', (e) => {
    const panel = document.getElementById('details-panel');
    const sidebar = document.getElementById('sidebar');
    if (panel && !panel.classList.contains('hidden') && !sidebar.contains(e.target) && !e.target.classList.contains('node')) {
        panel.classList.add('hidden');
    }
});
