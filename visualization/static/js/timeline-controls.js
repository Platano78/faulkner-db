class TimelineControls {
    constructor(timeline) {
        this.timeline = timeline;
    }

    init() {
        const playButton = document.getElementById('play-button');
        const exportButton = document.getElementById('export-button');

        if (playButton) {
            playButton.addEventListener('click', () => {
                alert('Animation feature coming soon!');
            });
        }

        if (exportButton) {
            exportButton.addEventListener('click', () => {
                if (this.timeline && this.timeline.filteredData) {
                    const blob = new Blob([JSON.stringify(this.timeline.filteredData, null, 2)], 
                        {type: 'application/json'});
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = 'timeline-export.json';
                    a.click();
                    URL.revokeObjectURL(url);
                }
            });
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    setTimeout(() => {
        if (window.timeline) {
            const controls = new TimelineControls(window.timeline);
            controls.init();
        }
    }, 500);
});
