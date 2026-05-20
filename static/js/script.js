document.addEventListener('DOMContentLoaded', () => {
    
    // Theme Toggle Logic
    const themeToggleBtn = document.getElementById('theme-toggle');
    if (themeToggleBtn) {
        const icon = themeToggleBtn.querySelector('i');
        
        // Check local storage for theme
        const currentTheme = localStorage.getItem('theme') || 'light';
        document.documentElement.setAttribute('data-theme', currentTheme);
        updateThemeIcon(currentTheme, icon);

        themeToggleBtn.addEventListener('click', () => {
            let theme = document.documentElement.getAttribute('data-theme');
            let newTheme = theme === 'dark' ? 'light' : 'dark';
            
            document.documentElement.setAttribute('data-theme', newTheme);
            localStorage.setItem('theme', newTheme);
            updateThemeIcon(newTheme, icon);
        });
    }

    function updateThemeIcon(theme, icon) {
        if (!icon) return;
        if (theme === 'dark') {
            icon.classList.remove('fa-moon');
            icon.classList.add('fa-sun');
        } else {
            icon.classList.remove('fa-sun');
            icon.classList.add('fa-moon');
        }
    }

    // Password Show/Hide Toggle
    const passwordToggles = document.querySelectorAll('.password-toggle');
    passwordToggles.forEach(toggle => {
        toggle.addEventListener('click', function() {
            const input = this.previousElementSibling;
            const icon = this.querySelector('i');
            
            if (input.type === 'password') {
                input.type = 'text';
                icon.classList.remove('fa-eye');
                icon.classList.add('fa-eye-slash');
            } else {
                input.type = 'password';
                icon.classList.remove('fa-eye-slash');
                icon.classList.add('fa-eye');
            }
        });
    });

    // Flash message auto-hide
    const alerts = document.querySelectorAll('.alert-dismissible');
    alerts.forEach(alert => {
        setTimeout(() => {
            if (typeof bootstrap !== 'undefined' && bootstrap.Alert) {
                const bsAlert = new bootstrap.Alert(alert);
                bsAlert.close();
            } else {
                alert.style.display = 'none';
            }
        }, 5000); // 5 seconds
    });

    // Form validation UI
    const forms = document.querySelectorAll('.needs-validation')
    Array.from(forms).forEach(form => {
        form.addEventListener('submit', event => {
            if (!form.checkValidity()) {
                event.preventDefault()
                event.stopPropagation()
            }
            form.classList.add('was-validated')
        }, false)
    });

    // Intelligent Skill Matcher: Animate SVG circular progress on load
    const progressRings = document.querySelectorAll('.match-ring-progress');
    progressRings.forEach(ring => {
        const percent = parseInt(ring.getAttribute('data-percent')) || 0;
        const radius = 60; // matching css dasharray
        const circumference = 2 * Math.PI * radius;
        
        // Calculate offset: circumference * (1 - pct / 100)
        const offset = circumference - (percent / 100) * circumference;
        
        // Animate stroke dashoffset
        setTimeout(() => {
            ring.style.strokeDashoffset = offset;
        }, 300);
    });

    // Recruiter Applicant Status: Dropdown AJAX Auto-submit
    const statusSelects = document.querySelectorAll('.applicant-status-select');
    statusSelects.forEach(select => {
        select.addEventListener('change', function() {
            const applicationId = this.getAttribute('data-app-id');
            const newStatus = this.value;
            const originalValue = this.getAttribute('data-original-val');
            
            // Highlight dropdown temporarily to show progress
            this.disabled = true;
            this.style.opacity = '0.6';
            
            fetch(`/recruiter/update_status/${applicationId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ status: newStatus })
            })
            .then(res => {
                if (!res.ok) throw new Error('Network response not ok');
                return res.json();
            })
            .then(data => {
                this.disabled = false;
                this.style.opacity = '1';
                
                if (data.success) {
                    this.setAttribute('data-original-val', newStatus);
                    
                    // Show a toast or notification success
                    showToast('Success', data.message, 'success');
                    
                    // Add dynamic row to history if the log container exists
                    const historyContainer = document.getElementById(`history-log-${applicationId}`);
                    if (historyContainer) {
                        const now = new Date();
                        const timeStr = now.toLocaleDateString('en-US', {month:'short', day:'numeric'}) + ' ' + now.toLocaleTimeString('en-US', {hour:'2-digit', minute:'2-digit'});
                        const noHistoryText = historyContainer.querySelector('.no-history');
                        if (noHistoryText) noHistoryText.remove();
                        
                        const logEntry = document.createElement('li');
                        logEntry.className = 'list-group-item d-flex justify-content-between align-items-center py-1 px-2 border-0 bg-transparent text-muted small';
                        logEntry.innerHTML = `<span><strong>${originalValue}</strong> &rarr; <strong>${newStatus}</strong></span> <span class="badge bg-light text-dark">${timeStr}</span>`;
                        historyContainer.appendChild(logEntry);
                    }
                } else {
                    this.value = originalValue; // revert dropdown
                    showToast('Error', data.message || 'Failed to update status', 'danger');
                }
            })
            .catch(err => {
                this.disabled = false;
                this.style.opacity = '1';
                this.value = originalValue; // revert dropdown
                showToast('Error', 'Connection failed. Status not updated.', 'danger');
                console.error('AJAX Error:', err);
            });
        });
    });

    // Helper to create and show floating toasts
    function showToast(title, message, type = 'success') {
        const toastContainer = document.getElementById('toast-container');
        if (!toastContainer) {
            // Create container if not exists
            const container = document.createElement('div');
            container.id = 'toast-container';
            container.className = 'toast-container position-fixed bottom-0 end-0 p-3';
            container.style.zIndex = '1100';
            document.body.appendChild(container);
        }
        
        const toastId = 'toast-' + Date.now();
        const iconClass = type === 'success' ? 'fa-circle-check text-success' : 'fa-triangle-exclamation text-danger';
        
        const toastHtml = `
            <div id="${toastId}" class="toast align-items-center border-0 shadow-lg" role="alert" aria-live="assertive" aria-atomic="true">
                <div class="d-flex">
                    <div class="toast-body d-flex align-items-center">
                        <i class="fa-solid ${iconClass} fs-5 me-2"></i>
                        <div>
                            <strong>${title}</strong>: ${message}
                        </div>
                    </div>
                    <button type="button" class="btn-close me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
                </div>
            </div>
        `;
        
        document.getElementById('toast-container').insertAdjacentHTML('beforeend', toastHtml);
        
        const toastEl = document.getElementById(toastId);
        if (type === 'success') {
            toastEl.style.backgroundColor = 'var(--bg-white)';
            toastEl.style.borderLeft = '4px solid #10b981';
        } else {
            toastEl.style.backgroundColor = 'var(--bg-white)';
            toastEl.style.borderLeft = '4px solid #ef4444';
        }
        
        if (typeof bootstrap !== 'undefined' && bootstrap.Toast) {
            const bsToast = new bootstrap.Toast(toastEl, { delay: 4000 });
            bsToast.show();
            toastEl.addEventListener('hidden.bs.toast', () => {
                toastEl.remove();
            });
        } else {
            // fallback if bootstrap toast not loaded
            toastEl.style.display = 'block';
            setTimeout(() => {
                toastEl.remove();
            }, 4000);
        }
    }

    // Candidate Profile and Resume upload loading indicators and anti-double submit logic
    const profileForm = document.getElementById('profile-form');
    if (profileForm) {
        profileForm.addEventListener('submit', function (e) {
            const submitBtn = this.querySelector('button[type="submit"]');
            if (submitBtn) {
                // Prevent duplicate submit
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Saving Profile...';
            }
        });
    }

    const resumeForm = document.getElementById('resume-form');
    if (resumeForm) {
        resumeForm.addEventListener('submit', function (e) {
            const submitBtn = this.querySelector('button[type="submit"]');
            if (submitBtn) {
                // Prevent duplicate submit
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Uploading...';
            }
        });
    }

    // INTERVIEW TYPE CONDITIONAL FIELDS TOGGLE
    const ivType = document.getElementById('iv-type');
    const meetingLinkGroup = document.getElementById('meeting-link-group');
    const officeAddressGroup = document.getElementById('office-address-group');
    if (ivType) {
        ivType.addEventListener('change', function() {
            if (this.value === 'Online') {
                meetingLinkGroup.classList.remove('d-none');
                officeAddressGroup.classList.add('d-none');
            } else if (this.value === 'Offline') {
                meetingLinkGroup.classList.add('d-none');
                officeAddressGroup.classList.remove('d-none');
            } else {
                meetingLinkGroup.classList.add('d-none');
                officeAddressGroup.classList.add('d-none');
            }
        });
    }

    // INTERVIEW TAB FOOTER SUBMIT TOGGLE
    const interviewTabs = document.getElementById('interviewTabs');
    if (interviewTabs) {
        const triggerTabList = [].slice.call(document.querySelectorAll('#interviewTabs button'));
        triggerTabList.forEach(function (triggerEl) {
            triggerEl.addEventListener('click', function (event) {
                const submitBtn = document.getElementById('submit-schedule-btn');
                if (event.target.id === 'direct-tab') {
                    submitBtn.classList.remove('d-none');
                } else {
                    submitBtn.classList.add('d-none');
                }
            });
        });
    }

    // SCHEDULE INTERVIEW BUTTON & SUGGESTED SLOTS INITIALIZER
    const scheduleBtns = document.querySelectorAll('.schedule-interview-btn');
    const scheduleModalEl = document.getElementById('scheduleInterviewModal');
    let scheduleModal = null;
    if (scheduleModalEl && typeof bootstrap !== 'undefined') {
        scheduleModal = new bootstrap.Modal(scheduleModalEl);
    }
    
    scheduleBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            const appId = this.getAttribute('data-app-id');
            const candidateName = this.getAttribute('data-candidate-name');
            const jobTitle = this.getAttribute('data-job-title');
            
            document.getElementById('schedule-app-id').value = appId;
            document.getElementById('modal-candidate-name').textContent = candidateName;
            document.getElementById('modal-job-title').textContent = jobTitle;
            
            // Load slots for application
            loadProposedSlots(appId);
            
            // Reset suggestion form
            const suggestForm = document.getElementById('suggest-slot-form');
            if (suggestForm) suggestForm.reset();
            
            // Switch to slots tab by default
            const suggestTab = document.getElementById('suggest-tab');
            if (suggestTab && typeof bootstrap !== 'undefined') {
                const tab = new bootstrap.Tab(suggestTab);
                tab.show();
            }
            
            // Hide submit btn by default since slots tab is active
            const submitBtn = document.getElementById('submit-schedule-btn');
            if (submitBtn) submitBtn.classList.add('d-none');
            
            if (scheduleModal) {
                scheduleModal.show();
            }
        });
    });

    // LOAD SLOTS FUNCTION
    function loadProposedSlots(appId) {
        const container = document.getElementById('slots-list-container');
        if (!container) return;
        
        container.innerHTML = `<tr><td colspan="5" class="text-center py-3"><span class="spinner-border spinner-border-sm text-primary me-2" role="status"></span>Loading proposed slots...</td></tr>`;
        
        fetch(`/recruiter/slots/${appId}`)
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                if (data.slots && data.slots.length > 0) {
                    let html = '';
                    data.slots.forEach(slot => {
                        let statusBadge = '';
                        let deleteBtn = '';
                        
                        if (slot.status === 'Pending') {
                            statusBadge = `<span class="badge bg-warning bg-opacity-10 text-warning px-2 py-1 rounded-pill">Pending</span>`;
                            deleteBtn = `<button type="button" class="btn btn-sm btn-outline-danger py-0 px-2 delete-slot-btn" data-slot-id="${slot.slot_id}"><i class="fa-solid fa-trash-can"></i></button>`;
                        } else if (slot.status === 'Accepted') {
                            statusBadge = `<span class="badge bg-success bg-opacity-10 text-success px-2 py-1 rounded-pill">Accepted</span>`;
                        } else {
                            statusBadge = `<span class="badge bg-secondary bg-opacity-10 text-secondary px-2 py-1 rounded-pill">${slot.status}</span>`;
                        }
                        
                        html += `
                            <tr>
                                <td class="small fw-semibold"><i class="fa-regular fa-calendar-check text-primary me-1"></i> ${slot.interview_time_str || slot.interview_time}</td>
                                <td>${slot.duration_minutes} mins</td>
                                <td class="text-truncate small" style="max-width: 150px;" title="${slot.location_details || ''}">${slot.location_details || 'N/A'}</td>
                                <td>${statusBadge}</td>
                                <td class="text-end">${deleteBtn}</td>
                            </tr>
                        `;
                    });
                    container.innerHTML = html;
                    
                    // Attach delete events
                    container.querySelectorAll('.delete-slot-btn').forEach(btn => {
                        btn.addEventListener('click', function() {
                            const slotId = this.getAttribute('data-slot-id');
                            if (confirm('Are you sure you want to delete this slot proposal?')) {
                                deleteProposedSlot(slotId, appId);
                            }
                        });
                    });
                } else {
                    container.innerHTML = `<tr><td colspan="5" class="text-center py-4 text-muted small"><i class="fa-solid fa-hourglass-empty me-1 d-block fs-4 mb-2 text-muted"></i>No proposed slots yet. Add one above!</td></tr>`;
                }
            } else {
                container.innerHTML = `<tr><td colspan="5" class="text-center text-danger py-3">Error: ${data.message}</td></tr>`;
            }
        })
        .catch(err => {
            console.error('Error loading slots:', err);
            container.innerHTML = `<tr><td colspan="5" class="text-center text-danger py-3">Failed to load slots.</td></tr>`;
        });
    }

    // SUBMIT SUGGESTED SLOT
    const addProposalBtn = document.getElementById('submit-suggest-slot-btn');
    if (addProposalBtn) {
        addProposalBtn.addEventListener('click', function() {
            const appId = document.getElementById('schedule-app-id').value;
            const timeVal = document.getElementById('slot-time').value;
            const durationVal = document.getElementById('slot-duration').value;
            const locationVal = document.getElementById('slot-location').value;
            
            if (!timeVal) {
                showToast('Warning', 'Please select a date and time.', 'danger');
                return;
            }
            
            this.disabled = true;
            this.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status"></span>Adding...';
            
            // Format time string to MySQL datetime (replace T with space)
            const formattedTime = timeVal.replace('T', ' ');
            
            fetch(`/recruiter/suggest_slot/${appId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    interview_time: formattedTime,
                    duration_minutes: durationVal,
                    location_details: locationVal
                })
            })
            .then(res => res.json())
            .then(data => {
                this.disabled = false;
                this.innerHTML = '<i class="fa-solid fa-plus me-1"></i> Add Proposal Slot';
                
                if (data.success) {
                    showToast('Success', data.message, 'success');
                    const suggestForm = document.getElementById('suggest-slot-form');
                    if (suggestForm) suggestForm.reset();
                    loadProposedSlots(appId);
                } else {
                    showToast('Error', data.message, 'danger');
                }
            })
            .catch(err => {
                this.disabled = false;
                this.innerHTML = '<i class="fa-solid fa-plus me-1"></i> Add Proposal Slot';
                showToast('Error', 'Connection error. Failed to add slot.', 'danger');
                console.error(err);
            });
        });
    }

    // DELETE SUGGESTED SLOT
    function deleteProposedSlot(slotId, appId) {
        fetch(`/recruiter/delete_slot/${slotId}`, {
            method: 'POST'
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                showToast('Success', data.message, 'success');
                loadProposedSlots(appId);
            } else {
                showToast('Error', data.message, 'danger');
            }
        })
        .catch(err => {
            showToast('Error', 'Connection error. Failed to delete slot.', 'danger');
            console.error(err);
        });
    }

    // DIRECT SCHEDULE INTERVIEW SUBMIT
    const submitScheduleBtn = document.getElementById('submit-schedule-btn');
    if (submitScheduleBtn) {
        submitScheduleBtn.addEventListener('click', function() {
            const appId = document.getElementById('schedule-app-id').value;
            const title = document.getElementById('iv-title').value;
            const type = document.getElementById('iv-type').value;
            const round = document.getElementById('iv-round').value;
            const timezone = document.getElementById('iv-timezone').value;
            const date = document.getElementById('iv-date').value;
            const start = document.getElementById('iv-start').value;
            const end = document.getElementById('iv-end').value;
            const meetingLink = document.getElementById('iv-meeting-link').value;
            const officeAddress = document.getElementById('iv-office-address').value;
            const interviewerName = document.getElementById('iv-interviewer-name').value;
            const interviewerEmail = document.getElementById('iv-interviewer-email').value;
            const contactPhone = document.getElementById('iv-contact-phone').value;
            const requiredDocs = document.getElementById('iv-required-docs').value;
            const instructions = document.getElementById('iv-instructions').value;
            
            if (!date || !start || !end) {
                showToast('Warning', 'Date, Start Time, and End Time are required.', 'danger');
                return;
            }
            
            this.disabled = true;
            this.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status"></span>Scheduling...';
            
            fetch(`/recruiter/schedule_interview/${appId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    interview_title: title,
                    interview_type: type,
                    interview_round: round,
                    timezone: timezone,
                    interview_date: date,
                    start_time: start,
                    end_time: end,
                    meeting_link: meetingLink,
                    office_address: officeAddress,
                    interviewer_name: interviewerName,
                    interviewer_email: interviewerEmail,
                    contact_phone: contactPhone,
                    required_documents: requiredDocs,
                    instructions: instructions
                })
            })
            .then(res => res.json())
            .then(data => {
                this.disabled = false;
                this.innerHTML = '<i class="fa-solid fa-paper-plane me-1"></i> Schedule & Send Invite';
                
                if (data.success) {
                    showToast('Success', 'Interview scheduled and email invitation sent successfully!', 'success');
                    if (scheduleModal) scheduleModal.hide();
                    setTimeout(() => {
                        location.reload();
                    }, 1500);
                } else {
                    showToast('Error', data.message, 'danger');
                }
            })
            .catch(err => {
                this.disabled = false;
                this.innerHTML = '<i class="fa-solid fa-paper-plane me-1"></i> Schedule & Send Invite';
                showToast('Error', 'Connection error. Failed to schedule.', 'danger');
                console.error(err);
            });
        });
    }

    // CANDIDATE ACCEPT INTERVIEW SLOT
    const acceptSlotBtns = document.querySelectorAll('.accept-slot-btn');
    acceptSlotBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            const slotId = this.getAttribute('data-slot-id');
            if (confirm('Are you sure you want to accept this interview slot? All other proposals will be declined and the interview will be booked.')) {
                this.disabled = true;
                this.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status"></span>Booking...';
                
                fetch(`/candidate/accept_slot/${slotId}`, {
                    method: 'POST'
                })
                .then(res => res.json())
                .then(data => {
                    if (data.success) {
                        showToast('Success', 'Interview slot accepted and booked successfully!', 'success');
                        setTimeout(() => {
                            location.reload();
                        }, 1500);
                    } else {
                        this.disabled = false;
                        this.innerHTML = '<i class="fa-solid fa-check me-1"></i> Accept Slot';
                        showToast('Error', data.message, 'danger');
                    }
                })
                .catch(err => {
                    this.disabled = false;
                    this.innerHTML = '<i class="fa-solid fa-check me-1"></i> Accept Slot';
                    showToast('Error', 'Connection error.', 'danger');
                    console.error(err);
                });
            }
        });
    });
    
    // CANDIDATE DECLINE INTERVIEW SLOT
    const declineSlotBtns = document.querySelectorAll('.decline-slot-btn');
    declineSlotBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            const slotId = this.getAttribute('data-slot-id');
            if (confirm('Are you sure you want to decline this slot suggestion?')) {
                this.disabled = true;
                this.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status"></span>Declining...';
                
                fetch(`/candidate/decline_slot/${slotId}`, {
                    method: 'POST'
                })
                .then(res => res.json())
                .then(data => {
                    if (data.success) {
                        showToast('Success', 'Slot suggestion declined successfully.', 'success');
                        setTimeout(() => {
                            location.reload();
                        }, 1500);
                    } else {
                        this.disabled = false;
                        this.innerHTML = '<i class="fa-solid fa-xmark me-1"></i> Decline';
                        showToast('Error', data.message, 'danger');
                    }
                })
                .catch(err => {
                    this.disabled = false;
                    this.innerHTML = '<i class="fa-solid fa-xmark me-1"></i> Decline';
                    showToast('Error', 'Connection error.', 'danger');
                    console.error(err);
                });
            }
        });
    });

    // CANCEL SCHEDULED INTERVIEW ACTION
    const cancelIvBtns = document.querySelectorAll('.cancel-interview-btn');
    cancelIvBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            const ivId = this.getAttribute('data-interview-id');
            if (confirm('Are you sure you want to cancel this scheduled interview? This will notify the candidate.')) {
                this.disabled = true;
                
                fetch(`/recruiter/cancel_interview/${ivId}`, {
                    method: 'POST'
                })
                .then(res => res.json())
                .then(data => {
                    if (data.success) {
                        showToast('Success', 'Interview cancelled successfully.', 'success');
                        setTimeout(() => {
                            location.reload();
                        }, 1500);
                    } else {
                        this.disabled = false;
                        showToast('Error', data.message, 'danger');
                    }
                })
                .catch(err => {
                    this.disabled = false;
                    showToast('Error', 'Connection error.', 'danger');
                    console.error(err);
                });
            }
        });
    });
});
