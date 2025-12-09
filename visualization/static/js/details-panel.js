function showNodeDetails(node) {
    const panel = document.getElementById('details-panel');
    const details = document.getElementById('node-details');
    
    details.innerHTML = `
        <h3>${node.title || node.id}</h3>
        <p><strong>Type:</strong> ${node.type || 'Unknown'}</p>
        <p><strong>ID:</strong> ${node.id}</p>
        ${node.timestamp ? `<p><strong>Date:</strong> ${new Date(node.timestamp).toLocaleString()}</p>` : ''}
        ${node.description ? `<p><strong>Description:</strong> ${node.description}</p>` : ''}
        ${node.project ? `<p><strong>Project:</strong> ${node.project}</p>` : ''}
    `;
    
    panel.classList.remove('hidden');
}

document.addEventListener('click', (e) => {
    const panel = document.getElementById('details-panel');
    const sidebar = document.getElementById('sidebar');
    if (panel && !panel.classList.contains('hidden') && !sidebar.contains(e.target) && !e.target.classList.contains('node')) {
        panel.classList.add('hidden');
    }
});
