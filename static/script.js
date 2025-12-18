document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('upload-form');
    const fileInput = document.getElementById('resume');
    const jobDescriptionInput = document.getElementById('job-description');
    const dropZone = document.getElementById('drop-zone');
    const fileNameDisplay = document.getElementById('file-name');
    const loader = document.getElementById('loader');
    const resultsContainer = document.getElementById('results-container');
    const resultsGrid = document.querySelector('.results-grid');


    const handleFile = (file) => {
        if (file) {
            fileNameDisplay.textContent = file.name;
            handleFileUpload(file);
        }
    };

    fileInput.addEventListener('change', () => handleFile(fileInput.files[0]));
    dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('dragover'); });
    dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        if (e.dataTransfer.files.length > 0) {
            fileInput.files = e.dataTransfer.files;
            handleFile(e.dataTransfer.files[0]);
        }
    });
    dropZone.addEventListener('click', () => fileInput.click());
    form.addEventListener('submit', (e) => e.preventDefault());

    async function handleFileUpload(file) {
        const formData = new FormData();
        formData.append('resume', file);
        formData.append('job_description', jobDescriptionInput.value); // Always send, even if empty

        loader.style.display = 'block';
        resultsContainer.style.display = 'none';

        try {
            const response = await fetch('/parse', {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'An unknown error occurred during parsing.');
            }

            const data = await response.json();
            updateResults(data);

        } catch (error) {
            console.error('Error:', error);
            alert('Failed to parse the resume: ' + error.message);
        } finally {
            // Hide loader and show results
            loader.style.display = 'none';
            resultsContainer.style.display = 'block';
        }
    }

    // Helper function to render fields that might be arrays or strings
    function renderField(elementId, data) {
        const element = document.getElementById(elementId);
        if (!element) {
            console.warn(`Element with ID '${elementId}' not found.`);
            return;
        }
        element.innerHTML = ''; // Clear previous content
        if (Array.isArray(data) && data.length > 0) {
            const list = document.createElement('ul');
            data.forEach(item => {
                const listItem = document.createElement('li');
                listItem.textContent = item;
                list.appendChild(listItem);
            });
            element.appendChild(list);
        } else if (typeof data === 'string' && data.trim()) { // Ensure string is not just whitespace
            element.textContent = data.trim();
        } else {
            element.textContent = 'Not Found';
        }
    }

    function updateResults(data) {
        renderField('result-summary', data.profile_summary); // New field for Profile Summary
        renderField('result-reasoning', data.scoring_reasoning); // New field for Scoring Reasoning
        renderField('result-name', data.name);
        renderField('result-email', data.email);
        renderField('result-phone', data.phone);
        renderField('result-education', data.education); // Education is now a list of strings
        renderField('result-skills', data.skills); // Skills is already a list of strings


        // Update ATS score circle
        const atsScore = data.match_percentage || 0;
        document.getElementById('result-ats-score').textContent = `${atsScore}%`;
        
        const progressCircle = document.getElementById('ats-progress-circle');
        const radius = progressCircle.r.baseVal.value;
        const circumference = 2 * Math.PI * radius;
        const offset = circumference - (atsScore / 100) * circumference;

        progressCircle.style.strokeDasharray = `${circumference} ${circumference}`;
        progressCircle.style.strokeDashoffset = offset;
        
        // Dynamically add/remove missing keywords card
        const missingKeywords = data.missing_keywords;
        let missingCard = document.getElementById('missing-keywords-card');
        
        // Remove old card if it exists
        if (missingCard) {
            missingCard.remove();
        }

        if (Array.isArray(missingKeywords) && missingKeywords.length > 0) {
            missingCard = document.createElement('div');
            missingCard.id = 'missing-keywords-card';
            missingCard.className = 'result-item'; // Use 'result-item' for consistent styling
            
            const title = document.createElement('h3');
            title.textContent = 'Missing Keywords';
            missingCard.appendChild(title);
            
            const list = document.createElement('ul');
            missingKeywords.forEach(item => {
                const listItem = document.createElement('li');
                listItem.textContent = item;
                list.appendChild(listItem);
            });
            missingCard.appendChild(list);
            resultsGrid.appendChild(missingCard);
        }
    }
});