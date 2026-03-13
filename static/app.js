// Data Vacuum Dashboard Logic

document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('vacuum-form');
    const runBtn = document.getElementById('run-btn');
    const btnText = runBtn.querySelector('.btn-text');
    const spinner = runBtn.querySelector('.spinner');

    const terminalBody = document.getElementById('terminal-output');

    const downloadSection = document.getElementById('download-section');
    const downloadCsv = document.getElementById('download-csv');
    const downloadParquet = document.getElementById('download-parquet');

    // Create ansi_up instance to parse terminal colors
    // We fetch it from CDN in HTML, if not loaded fallback to basic replace
    let ansi_up;
    if (typeof window.AnsiUp !== 'undefined') {
        ansi_up = new window.AnsiUp();
        ansi_up.use_classes = false; // output inline styles
    }

    // Helper to format logs
    function appendLog(text) {
        // Remove placeholder if it exists
        const placeholder = terminalBody.querySelector('.placeholder-text');
        if (placeholder) {
            placeholder.remove();
        }

        let htmlText;
        if (ansi_up) {
            htmlText = ansi_up.ansi_to_html(text);
        } else {
            // Very basic strip ansi fallback
            htmlText = text.replace(/\x1B\[[0-9;]*[mK]/g, '');
        }

        const div = document.createElement('div');
        div.innerHTML = htmlText || '&nbsp;';
        terminalBody.appendChild(div);

        // Auto-scroll to bottom
        terminalBody.scrollTop = terminalBody.scrollHeight;
    }

    function setFormState(isLoading) {
        const inputs = form.querySelectorAll('input, textarea');
        inputs.forEach(input => input.disabled = isLoading);
        runBtn.disabled = isLoading;

        if (isLoading) {
            btnText.textContent = 'Pipeline Running...';
            spinner.classList.remove('hidden');
            downloadSection.classList.add('hidden');
            terminalBody.innerHTML = '';
        } else {
            btnText.textContent = 'Launch Pipeline';
            spinner.classList.add('hidden');
        }
    }

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const prompt = document.getElementById('prompt').value;
        const labels = document.getElementById('labels').value;
        const maxQueries = parseInt(document.getElementById('max-queries').value, 10);
        const includeComments = document.getElementById('include-comments').checked;

        setFormState(true);
        appendLog('\x1b[1;36mInitializing Data Vacuum Pipeline...\x1b[0m');

        try {
            // First, trigger the run API
            const response = await fetch('/api/run', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    prompt,
                    labels,
                    max_queries: maxQueries,
                    include_comments: includeComments
                })
            });

            if (!response.ok) {
                throw new Error(`Server returned ${response.status}`);
            }

            const data = await response.json();
            const execId = data.exec_id;

            // Connect to SSE stream for logs
            const eventSource = new EventSource(`/api/stream/${execId}`);

            eventSource.onmessage = (event) => {
                appendLog(event.data);
            };

            eventSource.addEventListener('done', (event) => {
                const exitCode = parseInt(event.data, 10);
                eventSource.close();
                setFormState(false);

                if (exitCode === 0) {
                    // Success! Show downloads
                    downloadCsv.href = `/api/download/${execId}?type=csv`;
                    downloadParquet.href = `/api/download/${execId}?type=parquet`;
                    downloadSection.classList.remove('hidden');

                    // Add smooth scroll to downloads if on mobile
                    downloadSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                } else {
                    appendLog(`\n\x1b[1;31mPipeline failed with exit code ${exitCode}\x1b[0m`);
                }
            });

            eventSource.addEventListener('error', (event) => {
                // Ignore silent timeouts, but log real errors
                if (event.data) {
                    appendLog(`\n\x1b[1;31mStream error: ${event.data}\x1b[0m`);
                }
                eventSource.close();
                setFormState(false);
            });

        } catch (error) {
            appendLog(`\n\x1b[1;31mError launching pipeline: ${error.message}\x1b[0m`);
            setFormState(false);
        }
    });

    // Handle dynamically matching textarea height
    const promptArea = document.getElementById('prompt');
    promptArea.addEventListener('input', function () {
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight) + 'px';
    });
});
