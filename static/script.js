/**
 * SynapseCV - Client-side Frontend Controller
 * Controls dynamic role populating, file drag-drop, PDF.js parsing,
 * API submission, SVG score dials, skill chip generation, and A4 pdf exports.
 * Extended in Phase 4 for Concurrent Batch Uploads, Custom Templates, and Developer Portals.
 */

document.addEventListener("DOMContentLoaded", () => {
    // --- UI Element Selectors ---
    const uploadZone = document.getElementById("upload-zone");
    const fileInput = document.getElementById("file-input");
    const fileMetaCard = document.getElementById("file-meta-card");
    const fileNameEl = document.getElementById("file-name");
    const fileSizeEl = document.getElementById("file-size");
    const filePagesEl = document.getElementById("file-pages");
    const removeFileBtn = document.getElementById("remove-file-btn");
    
    const roleSelect = document.getElementById("role-select");
    const jdTextarea = document.getElementById("jd-textarea");
    const charCounter = document.getElementById("char-counter");
    
    const analyzeBtn = document.getElementById("analyze-btn");
    const uploadForm = document.getElementById("upload-form");
    
    const skeletonScreen = document.getElementById("skeleton-screen");
    const resultsContainer = document.getElementById("results-container");
    const emptyResultsState = document.getElementById("empty-results-state");
    const batchResultsContainer = document.getElementById("batch-results-container");
    const batchLeaderboardRows = document.getElementById("batch-leaderboard-rows");
    
    // Results DOM Elements
    const candidateNameEl = document.getElementById("res-candidate-name");
    const detectedRoleEl = document.getElementById("res-detected-role");
    const scoreNumberEl = document.getElementById("res-score-number");
    const radialFillEl = document.getElementById("res-radial-fill");
    
    const emailEl = document.getElementById("res-email");
    const phoneEl = document.getElementById("res-phone");
    const educationContainer = document.getElementById("res-education-container");
    
    const profileSummaryEl = document.getElementById("res-profile-summary");
    const matchedSkillsEl = document.getElementById("res-matched-skills");
    const missingSkillsEl = document.getElementById("res-missing-skills");
    
    const reasoningAccordion = document.getElementById("res-reasoning-accordion");
    const reasoningBodyEl = document.getElementById("res-reasoning-body");
    
    // Export Buttons
    const exportPdfBtn = document.getElementById("export-pdf-btn");
    const exportJsonBtn = document.getElementById("export-json-btn");
    const printReportBtn = document.getElementById("print-report-btn");
    
    const archivesListContainer = document.getElementById("archives-list-container");
    const saveTemplateBtn = document.getElementById("save-template-btn");

    let selectedFiles = []; // Phase 4: supports multiple files
    let parsedResultData = null; // Cache parsed JSON response
    let activeBatchData = null; // Cache batch results

    // CSRF helper
    const getCsrfToken = () => {
        const meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute("content") : "";
    };

    // XSS mitigation HTML escaper
    const escapeHtml = (str) => {
        if (!str) return "";
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    };

    // Configure PDF.js worker
    pdfjsLib.GlobalWorkerOptions.workerSrc = "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.4.120/pdf.worker.min.js";

    // Initialize Lucide icons
    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }

    // Custom Premium Confirmation Modal
    function showConfirm(message, options = {}) {
        return new Promise((resolve) => {
            const existingModal = document.getElementById("custom-confirm-modal");
            if (existingModal) existingModal.remove();

            const modal = document.createElement("div");
            modal.id = "custom-confirm-modal";
            modal.style.position = "fixed";
            modal.style.top = "0";
            modal.style.left = "0";
            modal.style.width = "100%";
            modal.style.height = "100%";
            modal.style.background = "rgba(10, 10, 15, 0.65)";
            modal.style.backdropFilter = "blur(12px)";
            modal.style.display = "flex";
            modal.style.alignItems = "center";
            modal.style.justifyContent = "center";
            modal.style.zIndex = "999999";
            modal.style.opacity = "0";
            modal.style.transition = "opacity 0.25s ease";

            const title = options.title || "Confirm Action";
            const confirmText = options.confirmText || "Confirm";
            const cancelText = options.cancelText || "Cancel";
            const isDanger = options.danger !== false;

            modal.innerHTML = `
                <div style="background: #11121b; border: 1px solid rgba(255,255,255,0.08); border-radius: 16px; width: 90%; max-width: 400px; padding: 1.5rem; box-shadow: 0 20px 40px rgba(0,0,0,0.5); transform: scale(0.9); transition: transform 0.25s cubic-bezier(0.34, 1.56, 0.64, 1);">
                     <div style="display: flex; align-items: center; gap: 0.75rem; margin-bottom: 1rem; border-bottom: 1px solid rgba(255,255,255,0.05); padding-bottom: 0.75rem;">
                        <div style="background: ${isDanger ? 'rgba(239, 68, 68, 0.12)' : 'rgba(0, 210, 211, 0.12)'}; color: ${isDanger ? '#ef4444' : 'var(--accent-secondary)'}; border-radius: 8px; width: 32px; height: 32px; display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
                            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">${isDanger ? '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" x2="12" y1="9" y2="13"/><line x1="12" x2="12.01" y1="17" y2="17"/>' : '<circle cx="12" cy="12" r="10"/><line x1="12" x2="12" y1="16" y2="12"/><line x1="12" x2="12.01" y1="8" y2="8"/>'}</svg>
                        </div>
                        <h4 style="font-family: var(--font-heading); font-size: 0.9rem; font-weight: 700; color: white; margin: 0; text-transform: uppercase; letter-spacing: 0.05em;">${escapeHtml(title)}</h4>
                    </div>
                    <p style="font-size: 0.8rem; color: #a0aec0; line-height: 1.5; margin: 0 0 1.5rem 0;">${message}</p>
                    <div style="display: flex; gap: 0.6rem; justify-content: flex-end;">
                        <button type="button" id="confirm-modal-cancel" style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 8px; padding: 0.45rem 0.9rem; color: #a0aec0; font-size: 0.75rem; cursor: pointer; transition: all 0.2s ease;">${escapeHtml(cancelText)}</button>
                        <button type="button" id="confirm-modal-ok" style="background: ${isDanger ? '#ef4444' : 'var(--accent-secondary)'}; border: none; border-radius: 8px; padding: 0.45rem 0.9rem; color: white; font-weight: 600; font-size: 0.75rem; cursor: pointer; transition: all 0.2s ease; box-shadow: 0 4px 12px ${isDanger ? 'rgba(239, 68, 68, 0.2)' : 'rgba(0, 210, 211, 0.2)'};">${escapeHtml(confirmText)}</button>
                    </div>
                </div>
            `;

            document.body.appendChild(modal);

            setTimeout(() => {
                modal.style.opacity = "1";
                modal.firstElementChild.style.transform = "scale(1)";
            }, 10);

            const cancelBtn = modal.querySelector("#confirm-modal-cancel");
            const okBtn = modal.querySelector("#confirm-modal-ok");

            cancelBtn.addEventListener("mouseenter", () => {
                cancelBtn.style.background = "rgba(255,255,255,0.06)";
                cancelBtn.style.color = "white";
            });
            cancelBtn.addEventListener("mouseleave", () => {
                cancelBtn.style.background = "rgba(255,255,255,0.03)";
                cancelBtn.style.color = "#a0aec0";
            });

            okBtn.addEventListener("mouseenter", () => {
                okBtn.style.opacity = "0.9";
                okBtn.style.transform = "translateY(-1px)";
            });
            okBtn.addEventListener("mouseleave", () => {
                okBtn.style.opacity = "1";
                okBtn.style.transform = "none";
            });

            const cleanup = (result) => {
                modal.style.opacity = "0";
                modal.firstElementChild.style.transform = "scale(0.9)";
                setTimeout(() => {
                    modal.remove();
                }, 200);
                resolve(result);
            };

            cancelBtn.addEventListener("click", () => cleanup(false));
            okBtn.addEventListener("click", () => cleanup(true));
            modal.addEventListener("click", (e) => {
                if (e.target === modal) cleanup(false);
            });
        });
    }

    // ==========================================================================
    // 0. Zero-Scroll Workspace Tab Switchers
    // ==========================================================================
    // Sidebar Switchers
    const sidebarTabBtns = document.querySelectorAll(".sidebar-tab-btn");
    sidebarTabBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            const targetTab = btn.getAttribute("data-tab");
            sidebarTabBtns.forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            
            document.querySelectorAll(".sidebar-tab-content").forEach(content => {
                if (content.id === targetTab) {
                    content.classList.add("active");
                } else {
                    content.classList.remove("active");
                }
            });
        });
    });

    // Results Panel Sub-Tabs Switchers
    const resultsTabBtns = document.querySelectorAll(".results-tab-btn");
    resultsTabBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            const targetResTab = btn.getAttribute("data-res-tab");
            resultsTabBtns.forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            
            document.querySelectorAll(".results-tab-content").forEach(content => {
                if (content.id === targetResTab) {
                    content.classList.add("active");
                } else {
                    content.classList.remove("active");
                }
            });
        });
    });

    // ==========================================================================
    // 1. Curated Role Template Manager
    // ==========================================================================
    async function loadRoles() {
        try {
            const response = await fetch("/roles");
            if (!response.ok) throw new Error("Failed to fetch roles");
            const roles = await response.json();
            
            // Populate select dropdown
            roles.forEach(role => {
                const option = document.createElement("option");
                option.value = role;
                option.textContent = role;
                roleSelect.appendChild(option);
            });
        } catch (err) {
            console.error("Error loading curated role library templates: ", err);
        }
    }
    
    async function loadArchives() {
        if (!archivesListContainer) return;
        
        try {
            const response = await fetch("/archives");
            if (!response.ok) throw new Error("Failed to fetch archives");
            const archives = await response.json();
            
            archivesListContainer.innerHTML = "";
            
            if (archives.length === 0) {
                archivesListContainer.innerHTML = `
                    <div style="text-align: center; padding: 2rem 0; color: #718096; font-size: 0.95rem;">
                        No candidates saved in your archives yet.
                    </div>
                `;
                return;
            }
            
            archives.forEach(item => {
                const card = document.createElement("div");
                card.style.background = "rgba(255, 255, 255, 0.02)";
                card.style.border = "1px solid var(--border-color)";
                card.style.borderRadius = "12px";
                card.style.padding = "0.75rem 1rem";
                card.style.display = "flex";
                card.style.alignItems = "center";
                card.style.justifyContent = "space-between";
                card.style.gap = "0.75rem";
                card.style.cursor = "pointer";
                card.style.transition = "var(--transition-smooth)";
                
                card.addEventListener("mouseenter", () => {
                    card.style.borderColor = "var(--accent-primary)";
                    card.style.background = "rgba(108, 92, 231, 0.05)";
                });
                card.addEventListener("mouseleave", () => {
                    card.style.borderColor = "var(--border-color)";
                    card.style.background = "rgba(255, 255, 255, 0.02)";
                });
                
                card.addEventListener("click", (e) => {
                    if (e.target.closest('.delete-archive-btn')) return;
                    activeBatchData = null;
                    parsedResultData = item;
                    renderAnalysisResults(item);
                    showNotification(`Loaded archived analysis for ${item.name || "Candidate"}.`, "success");
                });
                
                const scoreColor = item.match_percentage >= 80 ? "#10b981" : (item.match_percentage >= 50 ? "#f59e0b" : "#ef4444");
                const textContainer = document.createElement("div");
                textContainer.style.minWidth = "0";
                textContainer.style.flex = "1";
                
                const nameDiv = document.createElement("div");
                nameDiv.style.fontWeight = "600";
                nameDiv.style.fontSize = "0.9rem";
                nameDiv.style.color = "white";
                nameDiv.style.whiteSpace = "nowrap";
                nameDiv.style.overflow = "hidden";
                nameDiv.style.textOverflow = "ellipsis";
                nameDiv.textContent = item.name || "Unknown Candidate";
                
                const roleDiv = document.createElement("div");
                roleDiv.style.fontSize = "0.75rem";
                roleDiv.style.color = "#718096";
                roleDiv.style.whiteSpace = "nowrap";
                roleDiv.style.overflow = "hidden";
                roleDiv.style.textOverflow = "ellipsis";
                roleDiv.style.marginTop = "0.15rem";
                roleDiv.textContent = item.target_role || item.detected_role || "Inferred Role";
                
                textContainer.appendChild(nameDiv);
                textContainer.appendChild(roleDiv);
                
                const rightContainer = document.createElement("div");
                rightContainer.style.display = "flex";
                rightContainer.style.alignItems = "center";
                rightContainer.style.gap = "0.75rem";
                
                const scoreSpan = document.createElement("span");
                scoreSpan.style.fontSize = "0.85rem";
                scoreSpan.style.fontWeight = "700";
                scoreSpan.style.color = scoreColor;
                scoreSpan.style.background = scoreColor + "15";
                scoreSpan.style.padding = "0.2rem 0.5rem";
                scoreSpan.style.borderRadius = "6px";
                scoreSpan.textContent = `${item.match_percentage || 0}%`;
                
                const deleteBtn = document.createElement("button");
                deleteBtn.className = "delete-archive-btn";
                deleteBtn.style.background = "none";
                deleteBtn.style.border = "none";
                deleteBtn.style.color = "#718096";
                deleteBtn.style.cursor = "pointer";
                deleteBtn.style.padding = "0.25rem";
                deleteBtn.style.display = "flex";
                deleteBtn.style.alignItems = "center";
                deleteBtn.style.justifyContent = "center";
                deleteBtn.style.borderRadius = "6px";
                deleteBtn.style.transition = "var(--transition-smooth)";
                deleteBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/><line x1="10" x2="10" y1="11" y2="17"/><line x1="14" x2="14" y1="11" y2="17"/></svg>`;
                
                rightContainer.appendChild(scoreSpan);
                rightContainer.appendChild(deleteBtn);
                
                card.appendChild(textContainer);
                card.appendChild(rightContainer);
                deleteBtn.addEventListener("mouseenter", () => {
                    deleteBtn.style.color = "#ef4444";
                    deleteBtn.style.background = "rgba(239, 68, 68, 0.1)";
                });
                deleteBtn.addEventListener("mouseleave", () => {
                    deleteBtn.style.color = "#718096";
                    deleteBtn.style.background = "none";
                });
                deleteBtn.addEventListener("click", async (e) => {
                    e.stopPropagation();
                    const confirmed = await showConfirm(`Are you sure you want to remove <strong>${escapeHtml(item.name || "Candidate")}</strong> from your archives?`, {
                        title: "Remove Candidate",
                        confirmText: "Remove",
                        danger: true
                    });
                    if (!confirmed) return;
                    
                    try {
                        const delResp = await fetch(`/archives/${item.id}`, {
                            method: "DELETE",
                            headers: {
                                "X-CSRFToken": getCsrfToken()
                            }
                        });
                        if (!delResp.ok) throw new Error("Failed to delete record");
                        
                        card.remove();
                        showNotification("Record removed from archives successfully.", "success");
                        
                        if (parsedResultData && parsedResultData.id === item.id) {
                            parsedResultData = null;
                            resultsContainer.classList.add("hidden-section");
                            emptyResultsState.classList.remove("hidden-section");
                        }
                        
                        if (archivesListContainer.children.length === 0) {
                            archivesListContainer.innerHTML = `
                                <div style="text-align: center; padding: 2rem 0; color: #718096; font-size: 0.95rem;">
                                    No candidates saved in your archives yet.
                                </div>
                            `;
                        }
                    } catch (dErr) {
                        console.error(dErr);
                        showNotification("Failed to delete candidate archive.", "error");
                    }
                });
                
                archivesListContainer.appendChild(card);
            });
        } catch (err) {
            console.error("Failed to load historical candidate archives: ", err);
        }
    }

    loadRoles();
    loadArchives();

    roleSelect.addEventListener("change", async (e) => {
        const selectedRole = e.target.value;
        if (!selectedRole) {
            jdTextarea.value = "";
            updateCharCount();
            return;
        }
        
        try {
            const response = await fetch(`/roles/template?role_name=${encodeURIComponent(selectedRole)}`);
            if (!response.ok) throw new Error("Template not found");
            const data = await response.json();
            
            jdTextarea.value = data.template;
            updateCharCount();
        } catch (err) {
            console.error("Error loading role template text: ", err);
        }
    });

    // Job Description Character Counter
    function updateCharCount() {
        const count = jdTextarea.value.length;
        charCounter.textContent = `${count.toLocaleString()}/5,000`;
        
        if (count > 5000) {
            charCounter.classList.add("error");
            analyzeBtn.disabled = true;
        } else {
            charCounter.classList.remove("error");
            validateForm();
        }
    }
    jdTextarea.addEventListener("input", updateCharCount);

    // ==========================================================================
    // 2. Drag & Drop File Handling
    // ==========================================================================
    ["dragenter", "dragover"].forEach(eventName => {
        uploadZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            uploadZone.classList.add("dragover");
        }, false);
    });

    ["dragleave", "drop"].forEach(eventName => {
        uploadZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            uploadZone.classList.remove("dragover");
        }, false);
    });

    uploadZone.addEventListener("drop", (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files.length > 0) {
            handleFileSelection(files);
        }
    });

    uploadZone.addEventListener("click", () => fileInput.click());

    fileInput.addEventListener("change", (e) => {
        if (e.target.files.length > 0) {
            handleFileSelection(e.target.files);
        }
    });

    function handleFileSelection(files) {
        // Enforce PDF-only filters
        const validPDFs = Array.from(files).filter(file => file.name.toLowerCase().endsWith(".pdf"));
        
        if (validPDFs.length === 0) {
            showNotification("Invalid file format. Only standard PDF resumes are accepted.", "error");
            return;
        }
        
        if (validPDFs.length > 10) {
            showNotification("Batch uploading is limited to 10 resumes max.", "warning");
            selectedFiles = validPDFs.slice(0, 10);
        } else {
            selectedFiles = validPDFs;
        }
        
        if (selectedFiles.length === 1) {
            const file = selectedFiles[0];
            fileNameEl.textContent = file.name;
            fileSizeEl.textContent = formatBytes(file.size);
            filePagesEl.textContent = "Counting pages...";
            
            // Count Pages dynamically via PDF.js
            const fileReader = new FileReader();
            fileReader.onload = function() {
                const typedarray = new Uint8Array(this.result);
                pdfjsLib.getDocument(typedarray).promise.then(pdf => {
                    filePagesEl.textContent = `${pdf.numPages} ${pdf.numPages === 1 ? 'page' : 'pages'}`;
                }).catch(err => {
                    console.error("PDF.js count failed: ", err);
                    filePagesEl.textContent = "PDF Format";
                });
            };
            fileReader.readAsArrayBuffer(file);
        } else {
            // Batch description display
            fileNameEl.textContent = `Selected: ${selectedFiles.length} resumes`;
            const totalBytes = selectedFiles.reduce((acc, f) => acc + f.size, 0);
            fileSizeEl.textContent = formatBytes(totalBytes) + " Combined";
            filePagesEl.textContent = "Concurrent multi-threaded scan ready";
        }
        
        // Render Meta Card
        fileMetaCard.classList.remove("hidden-section");
        validateForm();
    }

    removeFileBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        selectedFiles = [];
        fileInput.value = "";
        fileMetaCard.classList.add("hidden-section");
        validateForm();
    });

    function formatBytes(bytes, decimals = 2) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const dm = decimals < 0 ? 0 : decimals;
        const sizes = ['Bytes', 'KB', 'MB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
    }

    function validateForm() {
        const isFileLoaded = selectedFiles.length > 0;
        const jdLength = jdTextarea.value.trim().length;
        const isJdValid = jdLength <= 5000;
        
        analyzeBtn.disabled = !(isFileLoaded && isJdValid);
    }

    // ==========================================================================
    // 3. API Parse Submission & Loading states
    // ==========================================================================
    uploadForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        if (selectedFiles.length === 0) return;

        // Reset UI States
        emptyResultsState.classList.add("hidden-section");
        resultsContainer.classList.add("hidden-section");
        if (batchResultsContainer) batchResultsContainer.classList.add("hidden-section");
        skeletonScreen.classList.remove("hidden-section");
        
        analyzeBtn.disabled = true;
        analyzeBtn.innerHTML = `<span class="skeleton-row" style="width: 20px; height: 20px; border-radius: 50%; margin: 0; display: inline-block;"></span> Analyzing...`;

        const formData = new FormData();
        selectedFiles.forEach(file => {
            formData.append("resume", file);
        });
        formData.append("job_description", jdTextarea.value.trim());
        // Send the selected template role name so backend can store target_role correctly
        const selectedRoleName = roleSelect ? roleSelect.value.replace(/^★\s*/, '').trim() : '';
        formData.append("selected_role", selectedRoleName);

        try {
            const response = await fetch("/parse", {
                method: "POST",
                headers: {
                    "X-CSRFToken": getCsrfToken()
                },
                body: formData
            });

            const rawBody = await response.text();
            let data = {};
            try {
                data = rawBody ? JSON.parse(rawBody) : {};
            } catch (parseErr) {
                console.error("Non-JSON parser response:", rawBody, parseErr);
                data = {
                    error: `Server returned ${response.status}. Check Render logs for the /parse request.`
                };
            }
            
            if (!response.ok) {
                throw new Error(data.error || "Failed to analyze resume profile.");
            }

            if (data.is_batch) {
                activeBatchData = data;
                renderBatchLeaderboard(data.results);
            } else {
                activeBatchData = null;
                parsedResultData = data;
                renderAnalysisResults(data);
            }

            if (archivesListContainer) {
                loadArchives();
            }

        } catch (err) {
            console.error(err);
            showNotification(err.message, "error");
            skeletonScreen.classList.add("hidden-section");
            emptyResultsState.classList.remove("hidden-section");
        } finally {
            analyzeBtn.disabled = false;
            analyzeBtn.innerHTML = `
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>
                Analyze Resume
            `;
            validateForm();
        }
    });

    // ==========================================================================
    // 4. Score Animation & Dynamic Renderers
    // ==========================================================================
    function renderAnalysisResults(data) {
        // Reset sub-tabs to Fit Overview
        const overviewTabBtn = document.querySelector('[data-res-tab="overview-res-tab"]');
        if (overviewTabBtn) {
            overviewTabBtn.click();
        }

        // Transition Screens
        emptyResultsState.classList.add("hidden-section");
        skeletonScreen.classList.add("hidden-section");
        if (batchResultsContainer) batchResultsContainer.classList.add("hidden-section");
        resultsContainer.classList.remove("hidden-section");

        // UI Back to Leaderboard button management
        let backBtn = document.getElementById("batch-back-to-leaderboard-btn");
        if (activeBatchData) {
            if (!backBtn) {
                backBtn = document.createElement("button");
                backBtn.id = "batch-back-to-leaderboard-btn";
                backBtn.type = "button";
                backBtn.className = "btn-secondary";
                backBtn.style.margin = "0 0 1.25rem 0";
                backBtn.style.width = "auto";
                backBtn.style.display = "flex";
                backBtn.style.alignItems = "center";
                backBtn.style.gap = "0.5rem";
                backBtn.style.background = "rgba(0, 210, 211, 0.1)";
                backBtn.style.borderColor = "rgba(0, 210, 211, 0.3)";
                backBtn.style.color = "var(--accent-secondary)";
                backBtn.style.fontWeight = "600";
                
                backBtn.innerHTML = `
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="m15 18-6-6 6-6"/></svg>
                    Back to Leaderboard
                `;
                backBtn.addEventListener("click", () => {
                    resultsContainer.classList.add("hidden-section");
                    batchResultsContainer.classList.remove("hidden-section");
                });
                resultsContainer.insertBefore(backBtn, resultsContainer.firstChild);
            } else {
                backBtn.style.display = "flex";
            }
        } else if (backBtn) {
            backBtn.style.display = "none";
        }

        // 4.1 Demographic block
        candidateNameEl.textContent = data.name || "Not Found";
        
        detectedRoleEl.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="m4.93 4.93 4.24 4.24M14.83 9.17l4.24-4.24M14.83 14.83l4.24 4.24M9.17 14.83l-4.24 4.24"/></svg> `;
        const roleSpan = document.createElement("span");
        roleSpan.textContent = data.target_role || data.detected_role || "Inferred Role";
        detectedRoleEl.appendChild(roleSpan);
        
        emailEl.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/></svg> `;
        const emailSpan = document.createElement("span");
        emailSpan.textContent = data.email || "Not Found";
        emailEl.appendChild(emailSpan);

        phoneEl.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/></svg> `;
        const phoneSpan = document.createElement("span");
        phoneSpan.textContent = data.phone || "Not Found";
        phoneEl.appendChild(phoneSpan);

        // GitHub & LinkedIn links
        const githubEl = document.getElementById("res-github");
        const linkedinEl = document.getElementById("res-linkedin");

        const isSafeUrl = (urlStr, allowedDomain) => {
            if (!urlStr) return false;
            try {
                const fullUrl = (urlStr.startsWith('http://') || urlStr.startsWith('https://')) ? urlStr : 'https://' + urlStr;
                const parsed = new URL(fullUrl);
                if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') return false;
                const host = parsed.hostname.toLowerCase();
                return host === allowedDomain || host.endsWith('.' + allowedDomain);
            } catch (e) {
                return false;
            }
        };

        if (githubEl) {
            const ghUrl = data.github_url || data.github || "";
            if (ghUrl && ghUrl.toLowerCase() !== "not found" && ghUrl !== "" && isSafeUrl(ghUrl, "github.com")) {
                githubEl.style.display = "flex";
                githubEl.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 6-2 6-5.5.08-1.25-.27-2.48-1-3.5.28-1.15.28-2.35 0-3.5 0 0-1 0-3 1.5-2.64-.5-5.36-.5-8 0C6 2 5 2 5 2c-.3 1.15-.3 2.35 0 3.5A5.403 5.403 0 0 0 4 9c0 3.5 3 5.5 6 5.5-.39.49-.68 1.05-.85 1.65-.17.6-.22 1.23-.15 1.85v4"/><path d="M9 18c-4.51 2-5-2-7-2"/></svg> `;
                const safeGhUrl = (ghUrl.startsWith('http://') || ghUrl.startsWith('https://')) ? ghUrl : 'https://' + ghUrl;
                const a = document.createElement("a");
                a.href = safeGhUrl;
                a.target = "_blank";
                a.rel = "noopener";
                a.style.color = "#a0aec0";
                a.style.textDecoration = "none";
                a.textContent = ghUrl.replace('https://github.com/', '').replace('https://', '');
                githubEl.appendChild(a);
            } else {
                githubEl.style.display = "none";
            }
        }
        if (linkedinEl) {
            const liUrl = data.linkedin_url || data.linkedin || "";
            if (liUrl && liUrl.toLowerCase() !== "not found" && liUrl !== "" && isSafeUrl(liUrl, "linkedin.com")) {
                linkedinEl.style.display = "flex";
                linkedinEl.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z"/><rect width="4" height="12" x="2" y="9"/><circle cx="4" cy="4" r="2"/></svg> `;
                const safeLiUrl = (liUrl.startsWith('http://') || liUrl.startsWith('https://')) ? liUrl : 'https://' + liUrl;
                const a = document.createElement("a");
                a.href = safeLiUrl;
                a.target = "_blank";
                a.rel = "noopener";
                a.style.color = "#a0aec0";
                a.style.textDecoration = "none";
                a.textContent = liUrl.replace('https://www.linkedin.com/in/', '').replace('https://', '');
                linkedinEl.appendChild(a);
            } else {
                linkedinEl.style.display = "none";
            }
        }

        // Education pills
        educationContainer.innerHTML = "";
        if (data.education && Array.isArray(data.education) && data.education.length > 0) {
            data.education.forEach(edu => {
                if (edu && edu.toLowerCase() !== "not found") {
                    const pill = document.createElement("div");
                    pill.className = "education-pill";
                    let cleanEdu = edu
                        .replace(/[\[\(\{\s]*(\d+(?:\.\d+)?\s*%)[\]\)\}\s]*/g, ' $1 ')
                        .replace(/([\[\(])\s*/g, ' ($1'.replace(/[\[\(]/g, ''))
                        .replace(/\s*([\]\)])\s*/g, ') ')
                        .replace(/—/g, ' — ')
                        .replace(/-/g, ' - ')
                        .replace(/&/g, ' & ')
                        .replace(/\s*,\s*/g, ', ')
                        .replace(/\(\s*([^)]+)\s*\)/g, '($1)')
                        .replace(/\s{2,}/g, ' ')
                        .trim();
                    pill.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21.42 10.922a1 1 0 0 0-.019-1.838L12.83 5.18a2 2 0 0 0-1.66 0L2.6 9.08a1 1 0 0 0 0 1.832l8.57 3.908a2 2 0 0 0 1.66 0z"/><path d="M6 12v5c0 2 2 3 6 3s6-1 6-3v-5"/></svg> `;
                    const eduSpan = document.createElement("span");
                    eduSpan.textContent = cleanEdu;
                    pill.appendChild(eduSpan);
                    educationContainer.appendChild(pill);
                }
            });
        }
        if (educationContainer.children.length === 0) {
            const noEdu = document.createElement("div");
            noEdu.className = "contact-item";
            noEdu.textContent = "No Education records found.";
            educationContainer.appendChild(noEdu);
        }

        // 4.2 Score Radial Fill & Color Styling
        const targetScore = parseInt(data.match_percentage || 0);
        animateScoreDial(targetScore);

        // 4.3 Summary
        profileSummaryEl.textContent = data.profile_summary || "No candidate profile overview provided.";

        // 4.3b ATS Optimization & Hygiene Checklist
        const hasEmail = data.email && data.email.toLowerCase() !== "not found" && data.email.includes("@");
        const hasPhone = data.phone && data.phone.toLowerCase() !== "not found";
        
        if (hasEmail && hasPhone) {
            setChecklistState("contact", "Optimal", "success");
        } else if (hasEmail || hasPhone) {
            setChecklistState("contact", "Partial", "warning");
        } else {
            setChecklistState("contact", "Missing details", "danger");
        }

        const score = parseInt(data.match_percentage || 0);
        if (score >= 70) {
            setChecklistState("skills", "Strong alignment", "success");
        } else if (score >= 45) {
            setChecklistState("skills", "Fair match", "warning");
        } else {
            setChecklistState("skills", "Weak match", "danger");
        }

        const scoreReasoning = (data.scoring_reasoning || "").toLowerCase();
        const hasVagueWarning = scoreReasoning.includes("vague") || scoreReasoning.includes("metric") || scoreReasoning.includes("quantifiable");
        if (hasVagueWarning) {
            setChecklistState("metrics", "Add metrics", "warning");
        } else {
            setChecklistState("metrics", "Excellent", "success");
        }

        const hasEducation = data.education && Array.isArray(data.education) && data.education.length > 0 && data.education[0].toLowerCase() !== "not found";
        if (hasEducation) {
            setChecklistState("structure", "Accredited", "success");
        } else {
            setChecklistState("structure", "Incomplete structures", "warning");
        }

        // 4.4 Technical Skill Chips splitting
        matchedSkillsEl.innerHTML = "";
        missingSkillsEl.innerHTML = "";

        const allSkills = data.skills || [];
        const missingCore = data.missing_keywords || [];

        // Dynamic filled chips
        if (allSkills.length > 0) {
            allSkills.forEach(skill => {
                const chip = document.createElement("span");
                chip.className = "skill-chip match";
                chip.textContent = skill;
                matchedSkillsEl.appendChild(chip);
            });
        } else {
            matchedSkillsEl.innerHTML = `<span class="upload-subtext">No skills detected.</span>`;
        }

        // Outlined red warning chips
        if (missingCore.length > 0) {
            missingCore.forEach(skill => {
                const chip = document.createElement("span");
                chip.className = "skill-chip missing";
                chip.textContent = skill;
                missingSkillsEl.appendChild(chip);
            });
        } else {
            missingSkillsEl.innerHTML = `<span class="upload-subtext" style="color: var(--color-green);">Perfect fit! No missing core keywords identified.</span>`;
        }

        // 4.5 AI Deductions reasoning text
        reasoningBodyEl.textContent = data.scoring_reasoning || "Deductive scoring summary unavailable.";

        // 4.5b Sync deduction final score with match percentage
        const deductionScoreEl = document.getElementById("deduction-final-score");
        if (deductionScoreEl) {
            deductionScoreEl.textContent = data.match_percentage || 0;
        }
        
        // Re-run Lucide in case custom elements added
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    }

    function animateScoreDial(score) {
        // Counter count-up effect
        let currentCount = 0;
        const duration = 1500; // matching SVG CSS transition
        const startTime = performance.now();

        function countUp(timestamp) {
            const elapsed = timestamp - startTime;
            const progress = Math.min(elapsed / duration, 1);
            currentCount = Math.floor(progress * score);
            scoreNumberEl.textContent = currentCount;

            if (progress < 1) {
                requestAnimationFrame(countUp);
            }
        }
        requestAnimationFrame(countUp);

        // Gauge Styling Grading classes
        radialFillEl.classList.remove("green", "amber", "red");
        if (score >= 80) {
            radialFillEl.classList.add("green");
        } else if (score >= 50) {
            radialFillEl.classList.add("amber");
        } else {
            radialFillEl.classList.add("red");
        }

        // Set Radial strokeoffset dynamically: circumference = 377
        const circumference = 377;
        const offset = circumference - (circumference * score) / 100;
        radialFillEl.style.strokeDashoffset = offset;
    }

    // ==========================================================================
    // 5. Accordion Event Listeners (Legacy — accordion replaced with inline panel)
    // ==========================================================================
    if (reasoningAccordion) {
        reasoningAccordion.addEventListener("click", () => {
            const isOpening = !reasoningAccordion.classList.contains("open");
            const bodyWrapper = reasoningAccordion.querySelector(".accordion-content");
            if (!bodyWrapper) return;
            
            if (isOpening) {
                reasoningAccordion.classList.add("open");
                bodyWrapper.style.maxHeight = bodyWrapper.scrollHeight + "px";
            } else {
                reasoningAccordion.classList.remove("open");
                bodyWrapper.style.maxHeight = "0px";
            }
        });
    }

    // ==========================================================================
    // 6. Export Features (A4 PDF, JSON data, and standard Print layout)
    // ==========================================================================
    exportPdfBtn.addEventListener("click", () => {
        if (!parsedResultData) return;
        
        try {
            const { jsPDF } = window.jspdf;
            const doc = new jsPDF({
                orientation: "portrait",
                unit: "mm",
                format: "a4"
            });

            // Branding details
            doc.setFillColor(6, 6, 9); // dark BG
            doc.rect(0, 0, 210, 297, "F");

            // Header Banner
            doc.setFillColor(108, 92, 231); // Accent Purple
            doc.rect(0, 0, 210, 45, "F");

            doc.setTextColor(255, 255, 255);
            doc.setFont("Helvetica", "bold");
            doc.setFontSize(24);
            doc.text("SYNAPSECV PROFILE ANALYSIS", 15, 20);

            doc.setFontSize(10);
            doc.setFont("Helvetica", "normal");
            doc.text(`Generated on ${new Date().toLocaleDateString()} | GDPR Encrypted Record`, 15, 28);

            // Left Sidebar Card: Match score
            doc.setFillColor(22, 22, 33);
            doc.rect(15, 60, 55, 55, "F");

            doc.setFontSize(36);
            doc.setFont("Helvetica", "bold");
            doc.setTextColor(255, 255, 255);
            const score = parsedResultData.match_percentage || 0;
            doc.text(`${score}%`, 25, 90);

            doc.setFontSize(10);
            doc.setTextColor(160, 160, 176);
            doc.text("MATCH RATING", 26, 102);

            // Right Info Block
            doc.setTextColor(255, 255, 255);
            doc.setFontSize(18);
            doc.setFont("Helvetica", "bold");
            doc.text(parsedResultData.name || "Candidate Name", 80, 70);

            doc.setFontSize(12);
            doc.setTextColor(0, 210, 211); // Neon Cyan
            doc.text(parsedResultData.target_role || parsedResultData.detected_role || "Inferred Role", 80, 80);

            doc.setFontSize(10);
            doc.setTextColor(226, 232, 240);
            doc.text(`Email: ${parsedResultData.email || "Not Found"}`, 80, 92);
            doc.text(`Phone: ${parsedResultData.phone || "Not Found"}`, 80, 98);

            // Profile Summary Section
            doc.setFillColor(22, 22, 33);
            doc.rect(15, 130, 180, 40, "F");

            doc.setTextColor(108, 92, 231);
            doc.setFontSize(11);
            doc.setFont("Helvetica", "bold");
            doc.text("PROFILE SUMMARY OVERVIEW", 20, 140);

            doc.setTextColor(203, 213, 224);
            doc.setFontSize(9.5);
            doc.setFont("Helvetica", "normal");
            
            const summary = parsedResultData.profile_summary || "No overview provided.";
            const splitSummary = doc.splitTextToSize(summary, 170);
            doc.text(splitSummary, 20, 148);

            // Skill Sets Details
            doc.setTextColor(255, 255, 255);
            doc.setFontSize(11);
            doc.setFont("Helvetica", "bold");
            doc.text("DETECTED SKILL ARRAYS", 15, 190);

            doc.setTextColor(160, 160, 176);
            doc.setFontSize(9);
            doc.setFont("Helvetica", "normal");
            
            const skillsText = (parsedResultData.skills || []).join(", ");
            const splitSkills = doc.splitTextToSize(`Identified: ${skillsText}`, 180);
            doc.text(splitSkills, 15, 198);

            doc.setTextColor(239, 68, 68); // Red
            doc.setFontSize(11);
            doc.setFont("Helvetica", "bold");
            doc.text("CRITICAL KEYWORD GAPS DETECTED", 15, 220);

            doc.setTextColor(160, 160, 176);
            doc.setFontSize(9);
            doc.setFont("Helvetica", "normal");

            const missingText = (parsedResultData.missing_keywords || []).join(", ");
            const splitMissing = doc.splitTextToSize(missingText.length > 0 ? `Missing: ${missingText}` : "Perfect! No core keyword mismatches found.", 180);
            doc.text(splitMissing, 15, 228);

            // Footer branding
            doc.setFontSize(8);
            doc.setTextColor(74, 85, 104);
            doc.text("SynapseCV Enterprise Application (GDPR compliant). Content processed under strict local compliance rules.", 15, 285);

            // Save PDF
            const safeName = (parsedResultData.name || "candidate").replace(/[^a-z0-9]/gi, '_').toLowerCase();
            doc.save(`synapse_analysis_${safeName}.pdf`);
            showNotification("A4 PDF report downloaded successfully!", "success");

        } catch (err) {
            console.error("jsPDF generation crashed: ", err);
            showNotification("Failed to generate PDF download.", "error");
        }
    });

    exportJsonBtn.addEventListener("click", () => {
        if (!parsedResultData) return;
        
        try {
            const jsonString = JSON.stringify(parsedResultData, null, 4);
            const blob = new Blob([jsonString], { type: "application/json" });
            const url = URL.createObjectURL(blob);
            
            const link = document.createElement("a");
            const safeName = (parsedResultData.name || "candidate").replace(/[^a-z0-9]/gi, '_').toLowerCase();
            link.download = `synapse_data_${safeName}.json`;
            link.href = url;
            link.click();
            setTimeout(() => URL.revokeObjectURL(url), 100);
            showNotification("Structured JSON profile data exported successfully!", "success");
        } catch (err) {
            console.error("JSON downloader failed: ", err);
            showNotification("Failed to download JSON payload data.", "error");
        }
    });

    printReportBtn.addEventListener("click", () => {
        if (!parsedResultData) {
            showNotification("No analysis data to print. Run an analysis first.", "error");
            return;
        }
        window.print();
    });

    function setChecklistState(type, text, level) {
        const iconEl = document.getElementById(`chk-${type}-icon`);
        const statusEl = document.getElementById(`chk-${type}-status`);
        if (!iconEl || !statusEl) return;

        // Reset
        statusEl.className = "";
        statusEl.style.color = "";
        statusEl.style.background = "";

        if (level === "success") {
            iconEl.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>`;
            statusEl.textContent = text;
            statusEl.style.color = "#10b981";
            statusEl.style.background = "rgba(16, 185, 129, 0.08)";
        } else if (level === "warning") {
            iconEl.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" x2="12" y1="8" y2="12"/><line x1="12" x2="12.01" y1="16" y2="16"/></svg>`;
            statusEl.textContent = text;
            statusEl.style.color = "#f59e0b";
            statusEl.style.background = "rgba(245, 158, 11, 0.08)";
        } else {
            iconEl.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" x2="6" y1="6" y2="18"/><line x1="6" x2="18" y1="6" y2="18"/></svg>`;
            statusEl.textContent = text;
            statusEl.style.color = "#ef4444";
            statusEl.style.background = "rgba(239, 68, 68, 0.08)";
        }
    }

    // ==========================================================================
    // 7. Dynamic Leaderboard Rendering for Batch Uploads
    // ==========================================================================
    function renderBatchLeaderboard(results) {
        skeletonScreen.classList.add("hidden-section");
        resultsContainer.classList.add("hidden-section");
        batchResultsContainer.classList.remove("hidden-section");
        
        const countMeta = document.getElementById("batch-meta-count");
        if (countMeta) {
            countMeta.textContent = `${results.length} files`;
        }

        batchLeaderboardRows.innerHTML = "";

        if (results.length === 0) {
            batchLeaderboardRows.innerHTML = `
                <tr>
                    <td colspan="6" style="padding: 2rem; text-align: center; color: #718096;">
                        All batch scans failed to process successfully.
                    </td>
                </tr>
            `;
            return;
        }

        results.forEach((item, index) => {
            const tr = document.createElement("tr");
            tr.style.borderBottom = "1px solid var(--border-color)";
            tr.style.transition = "var(--transition-smooth)";
            tr.addEventListener("mouseenter", () => tr.style.background = "rgba(255,255,255,0.02)");
            tr.addEventListener("mouseleave", () => tr.style.background = "none");

            if (item.error) {
                const td1 = document.createElement("td");
                td1.style.padding = "1rem 0.75rem";
                td1.style.textAlign = "center";
                td1.style.color = "#ef4444";
                td1.style.fontWeight = "bold";
                td1.textContent = "-";

                const td2 = document.createElement("td");
                td2.style.padding = "1rem 0.75rem";
                td2.style.color = "#a0aec0";
                td2.style.fontFamily = "monospace";
                td2.textContent = item.filename;

                const td3 = document.createElement("td");
                td3.style.padding = "1rem 0.75rem";
                td3.style.color = "#ef4444";
                td3.colSpan = 3;
                td3.textContent = `Failed: ${item.error}`;

                const td4 = document.createElement("td");
                td4.style.padding = "1rem 0.75rem";
                td4.style.textAlign = "center";
                td4.textContent = "-";

                tr.appendChild(td1);
                tr.appendChild(td2);
                tr.appendChild(td3);
                tr.appendChild(td4);
            } else {
                const score = item.match_percentage || 0;
                const scoreColor = score >= 80 ? "#10b981" : (score >= 50 ? "#f59e0b" : "#ef4444");
                const skillsPreview = (item.skills || []).slice(0, 3).join(", ");
                const skillsText = skillsPreview ? (item.skills.length > 3 ? `${skillsPreview}...` : skillsPreview) : "None";

                const td1 = document.createElement("td");
                td1.style.padding = "1rem 0.75rem";
                td1.style.textAlign = "center";
                td1.style.fontWeight = "700";
                td1.style.color = "#718096";
                td1.textContent = `#${index + 1}`;

                const td2 = document.createElement("td");
                td2.style.padding = "1rem 0.75rem";
                td2.style.fontWeight = "600";
                td2.style.color = "white";
                td2.textContent = item.name || "Unknown";

                const td3 = document.createElement("td");
                td3.style.padding = "1rem 0.75rem";
                td3.style.color = "#cbd5e0";
                td3.textContent = item.target_role || item.detected_role || "Not Inferred";

                const td4 = document.createElement("td");
                td4.style.padding = "1rem 0.75rem";
                td4.style.textAlign = "center";
                const scoreSpan = document.createElement("span");
                scoreSpan.style.fontSize = "0.8rem";
                scoreSpan.style.fontWeight = "700";
                scoreSpan.style.color = scoreColor;
                scoreSpan.style.background = scoreColor + "15";
                scoreSpan.style.padding = "0.2rem 0.5rem";
                scoreSpan.style.borderRadius = "6px";
                scoreSpan.style.display = "inline-block";
                scoreSpan.textContent = `${score}%`;
                td4.appendChild(scoreSpan);

                const td5 = document.createElement("td");
                td5.style.padding = "1rem 0.75rem";
                td5.style.color = "#a0aec0";
                td5.style.maxWidth = "200px";
                td5.style.whiteSpace = "nowrap";
                td5.style.overflow = "hidden";
                td5.style.textOverflow = "ellipsis";
                td5.title = (item.skills || []).join(", ");
                td5.textContent = skillsText;

                const td6 = document.createElement("td");
                td6.style.padding = "1rem 0.75rem";
                td6.style.textAlign = "center";
                const inspectBtn = document.createElement("button");
                inspectBtn.className = "inspect-btn btn-secondary";
                inspectBtn.style.margin = "0";
                inspectBtn.style.padding = "0.35rem 0.65rem";
                inspectBtn.style.fontSize = "0.75rem";
                inspectBtn.style.width = "auto";
                inspectBtn.style.background = "rgba(0, 210, 211, 0.1)";
                inspectBtn.style.borderColor = "rgba(0, 210, 211, 0.3)";
                inspectBtn.style.color = "var(--accent-secondary)";
                inspectBtn.textContent = "Inspect";
                inspectBtn.addEventListener("click", () => {
                    parsedResultData = item;
                    renderAnalysisResults(item);
                    batchResultsContainer.classList.add("hidden-section");
                    resultsContainer.classList.remove("hidden-section");
                });
                td6.appendChild(inspectBtn);

                tr.appendChild(td1);
                tr.appendChild(td2);
                tr.appendChild(td3);
                tr.appendChild(td4);
                tr.appendChild(td5);
                tr.appendChild(td6);
            }
            batchLeaderboardRows.appendChild(tr);
        });
    }

    // ==========================================================================
    // 8. Custom Role Templates & API Keys Developer Portal
    // ==========================================================================
    if (saveTemplateBtn) {
        saveTemplateBtn.addEventListener("click", async () => {
            const jdText = jdTextarea.value.trim();
            if (!jdText) {
                showNotification("Please write or paste target job description criteria first.", "error");
                return;
            }

            const roleName = prompt("Enter custom role template name (e.g. Senior Backend Dev):");
            if (!roleName) return;

            try {
                const response = await fetch("/roles", {
                    method: "POST",
                    headers: { 
                        "Content-Type": "application/json",
                        "X-CSRFToken": getCsrfToken()
                    },
                    body: JSON.stringify({ role_name: roleName, job_description: jdText })
                });
                
                const resData = await response.json();
                if (!response.ok) throw new Error(resData.error || "Failed to save template.");

                showNotification(resData.message, "success");
                
                // Reset roleSelect and select new
                roleSelect.innerHTML = '<option value="">-- Custom Profile (Infer from Resume) --</option>';
                await loadRoles();
                roleSelect.value = `★ ${roleName}`;
            } catch (err) {
                console.error(err);
                showNotification(err.message, "error");
            }
        });
    }

    // API Keys logic
    const generateKeyBtn = document.getElementById("generate-key-btn");
    const apiKeyNameInput = document.getElementById("api-key-name-input");
    const apiKeysListContainer = document.getElementById("api-keys-list-container");
    const newKeyDisplayCard = document.getElementById("new-key-display-card");
    const plaintextKeyValue = document.getElementById("plaintext-key-value");
    const copyKeyBtn = document.getElementById("copy-key-btn");

    async function loadApiKeys() {
        if (!apiKeysListContainer) return;

        try {
            const response = await fetch("/api/v1/keys");
            if (!response.ok) throw new Error("Failed to fetch keys");
            const keys = await response.json();

            apiKeysListContainer.innerHTML = "";

            if (keys.length === 0) {
                apiKeysListContainer.innerHTML = `
                    <div style="text-align: center; padding: 1.5rem 0; color: #718096; font-size: 0.85rem;">
                        No active developer credentials found.
                    </div>
                `;
                return;
            }

            keys.forEach(k => {
                const keyRow = document.createElement("div");
                keyRow.style.background = "rgba(255, 255, 255, 0.02)";
                keyRow.style.border = "1px solid var(--border-color)";
                keyRow.style.borderRadius = "8px";
                keyRow.style.padding = "0.5rem 0.75rem";
                keyRow.style.display = "flex";
                keyRow.style.alignItems = "center";
                keyRow.style.justifyContent = "space-between";
                keyRow.style.fontSize = "0.8rem";

                keyRow.innerHTML = `
                    <div style="min-width: 0; flex: 1; padding-right: 0.5rem;">
                        <div style="font-weight: 600; color: white; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${escapeHtml(k.name)}</div>
                        <code style="font-size: 0.7rem; color: #718096; font-family: monospace;">${escapeHtml(k.key_prefix)}xxxx</code>
                    </div>
                    <button class="revoke-key-btn" style="background: none; border: none; color: #718096; cursor: pointer; padding: 0.25rem; display: flex; align-items: center; justify-content: center; border-radius: 4px; transition: var(--transition-smooth);">
                        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>
                    </button>
                `;

                const revokeBtn = keyRow.querySelector(".revoke-key-btn");
                revokeBtn.addEventListener("mouseenter", () => {
                    revokeBtn.style.color = "#ef4444";
                    revokeBtn.style.background = "rgba(239, 68, 68, 0.1)";
                });
                revokeBtn.addEventListener("mouseleave", () => {
                    revokeBtn.style.color = "#718096";
                    revokeBtn.style.background = "none";
                });
                revokeBtn.addEventListener("click", async () => {
                    const confirmed = await showConfirm(`Are you sure you want to revoke key "<strong>${escapeHtml(k.name)}</strong>"? This action cannot be undone.`, {
                        title: "Revoke API Key",
                        confirmText: "Revoke Key",
                        danger: true
                    });
                    if (!confirmed) return;

                    try {
                        const delResp = await fetch(`/api/v1/keys/${k.id}`, {
                            method: "DELETE",
                            headers: {
                                "X-CSRFToken": getCsrfToken()
                            }
                        });
                        if (!delResp.ok) throw new Error("Revocation failed");
                        keyRow.remove();
                        showNotification("API Key revoked successfully.", "success");
                        if (apiKeysListContainer.children.length === 0) {
                            apiKeysListContainer.innerHTML = `
                                <div style="text-align: center; padding: 1.5rem 0; color: #718096; font-size: 0.85rem;">
                                    No active developer credentials found.
                                </div>
                            `;
                        }
                    } catch (err) {
                        console.error(err);
                        showNotification("Failed to revoke API key.", "error");
                    }
                });

                apiKeysListContainer.appendChild(keyRow);
            });
        } catch (err) {
            console.error("Failed to load active API keys: ", err);
        }
    }

    if (generateKeyBtn) {
        generateKeyBtn.addEventListener("click", async () => {
            const keyName = apiKeyNameInput.value.trim() || "Production API Key";
            
            try {
                const response = await fetch("/api/v1/keys", {
                    method: "POST",
                    headers: { 
                        "Content-Type": "application/json",
                        "X-CSRFToken": getCsrfToken()
                    },
                    body: JSON.stringify({ name: keyName })
                });

                const data = await response.json();
                if (!response.ok) throw new Error(data.error || "Failed to generate key.");

                plaintextKeyValue.textContent = data.plaintext_key;
                newKeyDisplayCard.style.display = "block";
                apiKeyNameInput.value = "";
                showNotification("API key credentials created!", "success");
                loadApiKeys();
            } catch (err) {
                console.error(err);
                showNotification(err.message, "error");
            }
        });
    }

    if (copyKeyBtn) {
        copyKeyBtn.addEventListener("click", () => {
            const range = document.createRange();
            range.selectNode(plaintextKeyValue);
            window.getSelection().removeAllRanges();
            window.getSelection().addRange(range);
            try {
                document.execCommand("copy");
                showNotification("Copied credentials plaintext key to clipboard!", "success");
            } catch (err) {
                console.error("Clipboard copy failed: ", err);
            }
            window.getSelection().removeAllRanges();
        });
    }

    // Call developers keys loader — only when the dev portal elements exist (authenticated users)
    if (apiKeysListContainer) {
        loadApiKeys();
    }

    // ==========================================================================
    // 9. Batch Export Features (CSV & JSON Leaderboard Exports)
    // ==========================================================================
    const batchExportCsv = document.getElementById("batch-export-csv");
    const batchExportJson = document.getElementById("batch-export-json");

    if (batchExportJson) {
        batchExportJson.addEventListener("click", () => {
            if (!activeBatchData) return;
            try {
                const jsonString = JSON.stringify(activeBatchData.results, null, 4);
                const blob = new Blob([jsonString], { type: "application/json" });
                const url = URL.createObjectURL(blob);
                
                const link = document.createElement("a");
                link.download = `synapse_batch_results_${new Date().getTime()}.json`;
                link.href = url;
                link.click();
                setTimeout(() => URL.revokeObjectURL(url), 100);
                showNotification("Batch structured JSON profile data exported successfully!", "success");
            } catch (err) {
                console.error("JSON batch downloader failed: ", err);
                showNotification("Failed to export JSON batch results.", "error");
            }
        });
    }

    if (batchExportCsv) {
        batchExportCsv.addEventListener("click", () => {
            if (!activeBatchData) return;
            try {
                const results = activeBatchData.results.filter(r => !r.error);
                
                // Standard CSV Headers
                let csvRows = [
                    ["Rank", "Candidate Name", "Detected Role", "Fit Score", "Email", "Phone", "Technical Skills Identified", "Missing Keyword Gaps"].map(h => `"${h}"`).join(",")
                ];

                results.forEach((item, index) => {
                    const row = [
                        `"${index + 1}"`,
                        `"${(item.name || "Unknown").replace(/'/g, "''").replace(/"/g, '""')}"`,
                        `"${(item.target_role || item.detected_role || "").replace(/'/g, "''").replace(/"/g, '""')}"`,
                        `"${item.match_percentage || 0}%"`,
                        `"${item.email || ""}"`,
                        `"${item.phone || ""}"`,
                        `"${(item.skills || []).join(", ").replace(/'/g, "''").replace(/"/g, '""')}"`,
                        `"${(item.missing_keywords || []).join(", ").replace(/'/g, "''").replace(/"/g, '""')}"`
                    ];
                    csvRows.push(row.join(","));
                });

                const csvString = csvRows.join("\n");
                const blob = new Blob([csvString], { type: "text/csv;charset=utf-8;" });
                const url = URL.createObjectURL(blob);
                
                const link = document.createElement("a");
                link.download = `synapse_leaderboard_${new Date().getTime()}.csv`;
                link.href = url;
                link.click();
                setTimeout(() => URL.revokeObjectURL(url), 100);
                showNotification("Batch spreadsheet exported successfully!", "success");
            } catch (err) {
                console.error("CSV bulk downloader failed: ", err);
                showNotification("Failed to generate CSV export file.", "error");
            }
        });
    }

    // ==========================================================================
    // 10. Notification alerts
    // ==========================================================================
    function showNotification(message, type = "success") {
        const toast = document.createElement("div");
        toast.style.position = "fixed";
        toast.style.bottom = "2rem";
        toast.style.right = "2rem";
        toast.style.zIndex = "9999";
        toast.style.padding = "1rem 1.5rem";
        toast.style.borderRadius = "14px";
        toast.style.background = type === "success" ? "rgba(16, 185, 129, 0.95)" : "rgba(239, 68, 68, 0.95)";
        toast.style.backdropFilter = "blur(8px)";
        toast.style.color = "white";
        toast.style.fontWeight = "600";
        toast.style.fontSize = "0.9rem";
        toast.style.border = "1px solid rgba(255, 255, 255, 0.1)";
        toast.style.boxShadow = "0 10px 30px rgba(0,0,0,0.5)";
        toast.style.display = "flex";
        toast.style.alignItems = "center";
        toast.style.gap = "0.75rem";
        toast.style.animation = "slideUp 0.3s ease-out";
        
        toast.innerHTML = `
            ${type === "success" 
                ? '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>' 
                : '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" x2="12" y1="8" y2="12"/><line x1="12" x2="12.01" y1="16" y2="16"/></svg>'
            }
            <span>${escapeHtml(message)}</span>
        `;
        
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.style.animation = "fadeOut 0.3s ease-in";
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    }
});
