/*
 * Copyright (C) 2026 Redcar & Cleveland Borough Council
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License as published by
 * the Free Software Foundation, version 3.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */

/**
 * Members Enquiries - Main JavaScript File
 * Contains common functions and initialization code
 *
 * ALERT SYSTEM USAGE:
 * ===================
 *
 * Basic Alerts:
 * - showSuccess('Message')     // Green success alert
 * - showError('Message')       // Red error alert
 * - showWarning('Message')     // Yellow warning alert
 * - showInfo('Message')        // Blue info alert
 *
 * Advanced Alerts:
 * - showAlert('success', 'Message', { dismissTime: 3000, position: 'fixed-top' })
 *
 * Confirmation Dialogs:
 * - showConfirmation({
 *     title: 'Delete Item',
 *     message: 'Are you sure?',
 *     confirmText: 'Delete',
 *     confirmClass: 'btn-danger',
 *     onConfirm: function() { console.log('confirmed'); }
 *   })
 *
 * DO NOT USE: alert(), confirm(), or alertify.notify() - use the above functions instead
 */

// TinyMCE Dark Mode Setup Function (called by TinyMCE setup)
function setupTinyMCEDarkMode(editor) {
    // This function is called when TinyMCE initializes each editor
    editor.on('init', function() {
        // Apply current theme immediately when editor is ready
        const currentTheme = document.documentElement.getAttribute('data-bs-theme') || localStorage.getItem('theme') || 'light';
        applyTinyMCETheme(editor, currentTheme);
    });
}

function applyTinyMCETheme(editor, theme) {
    // Apply theme to a specific TinyMCE editor
    if (editor && editor.getDoc()) {
        const doc = editor.getDoc();
        const body = doc.body;
        
        if (theme === 'dark') {
            body.classList.add('dark-mode-content');
            body.classList.remove('light-mode-content');
            // Also set inline styles as backup
            body.style.setProperty('background-color', '#212529', 'important');
            body.style.setProperty('color', '#f8f9fa', 'important');
        } else {
            body.classList.add('light-mode-content');
            body.classList.remove('dark-mode-content');
            body.style.setProperty('background-color', '#ffffff', 'important');
            body.style.setProperty('color', '#212529', 'important');
        }
    }
}

// Make the function globally available for TinyMCE
window.setupTinyMCEDarkMode = setupTinyMCEDarkMode;

// Dark Mode Toggle Functions
function initDarkMode() {
    // Get saved theme from localStorage, then default to light
    const savedTheme = localStorage.getItem('theme') || 'light';
    
    const html = document.documentElement;
    
    // Apply saved theme
    html.setAttribute('data-bs-theme', savedTheme);
    updateThemeIcon(savedTheme);
    
    // Add click listener to toggle button - use more robust selection
    const themeToggle = document.getElementById('theme-toggle');
    if (themeToggle) {
        // Remove any existing listeners to prevent duplicates
        themeToggle.removeEventListener('click', toggleTheme);
        themeToggle.addEventListener('click', toggleTheme);
    }
    
    // Also try to find and fix any existing TinyMCE editors
    setTimeout(function() {
        updateTinyMCETheme(savedTheme);
    }, 500);
}

function toggleTheme() {
    const html = document.documentElement;
    const currentTheme = html.getAttribute('data-bs-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    
    // Apply new theme
    html.setAttribute('data-bs-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    
    updateThemeIcon(newTheme);
}


function updateThemeIcon(theme) {
    const themeIcon = document.getElementById('theme-icon');
    if (themeIcon) {
        if (theme === 'dark') {
            themeIcon.className = 'bi bi-sun';
            themeIcon.parentElement.title = 'Switch to light mode';
        } else {
            themeIcon.className = 'bi bi-moon-stars';
            themeIcon.parentElement.title = 'Switch to dark mode';
        }
    }
    
    // Update TinyMCE theme if it exists
    updateTinyMCETheme(theme);
}

function updateTinyMCETheme(theme) {
    // Method 1: Use the new TinyMCE-integrated approach
    if (typeof tinymce !== 'undefined' && tinymce.editors && tinymce.editors.length > 0) {
        tinymce.editors.forEach(function(editor) {
            applyTinyMCETheme(editor, theme);
        });
    }
    
    // Method 2: Direct iframe targeting with retry mechanism (fallback)
    function updateIframes(attempt = 0) {
        const iframes = document.querySelectorAll('.tox-edit-area iframe, iframe[id*="tiny"], iframe[id*="mce"]');
        let updated = 0;
        
        iframes.forEach(function(iframe) {
            try {
                const doc = iframe.contentDocument || iframe.contentWindow.document;
                const body = doc.body;
                if (body) {
                    if (theme === 'dark') {
                        body.style.setProperty('background-color', '#212529', 'important');
                        body.style.setProperty('color', '#f8f9fa', 'important');
                        body.classList.add('dark-mode-content');
                        body.classList.remove('light-mode-content');
                    } else {
                        body.style.setProperty('background-color', '#ffffff', 'important');
                        body.style.setProperty('color', '#212529', 'important');
                        body.classList.add('light-mode-content');
                        body.classList.remove('dark-mode-content');
                    }
                    updated++;
                }
            } catch (e) {
                // Cross-origin iframe access might fail, ignore
            }
        });
        
        // Retry if no iframes found and attempts < 3
        if (updated === 0 && attempt < 3) {
            setTimeout(function() {
                updateIframes(attempt + 1);
            }, 200 * (attempt + 1));
        }
    }
    
    updateIframes();
    
    // Method 3: Try again after a delay for late-loading editors
    setTimeout(function() {
        updateIframes();
    }, 1000);
}

// Initialize tooltips
function initTooltips() {
    try {
        const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    } catch (e) {
        console.error("Error initializing tooltips:", e);
    }
}

// Initialize popovers
function initPopovers() {
    try {
        const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
        popoverTriggerList.map(function (popoverTriggerEl) {
            return new bootstrap.Popover(popoverTriggerEl);
        });
    } catch (e) {
        console.error("Error initializing popovers:", e);
    }
}

// Format date fields to local format
function formatDateFields() {
    try {
        document.querySelectorAll('.format-date').forEach(function(element) {
            const date = new Date(element.textContent);
            if (!isNaN(date)) {
                element.textContent = date.toLocaleDateString();
            }
        });
    } catch (e) {
        console.error("Error formatting date fields:", e);
    }
}

// Handle Ajax form submissions
function setupAjaxForms() {
    try {
        document.querySelectorAll('form.ajax-form').forEach(function(form) {
            form.addEventListener('submit', function(e) {
                e.preventDefault();
                
                const formData = new FormData(form);
                const url = form.getAttribute('action');
                
                fetch(url, {
                    method: 'POST',
                    body: formData,
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        // Show success message
                        showSuccess('Operation completed successfully!');

                        // If a redirect URL is provided, go there
                        if (data.redirect) {
                            window.location.href = data.redirect;
                        } else {
                            // Otherwise refresh the current page
                            window.location.reload();
                        }
                    } else {
                        // Show error message
                        showError(data.message || 'An error occurred.');
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    showError('An unexpected error occurred.');
                });
            });
        });
    } catch (e) {
        console.error("Error setting up Ajax forms:", e);
    }
}

// Show alert message - Unified Toast System
function showAlert(type, message, options = {}) {
    try {
        // Redirect all alerts to the unified toast system
        if (typeof showToast === 'function') {
            // Map Bootstrap alert types to toast types
            const typeMap = {
                'danger': 'error',
                'success': 'success',
                'warning': 'warning',
                'info': 'info',
                'primary': 'info',
                'secondary': 'info'
            };

            const toastType = typeMap[type] || 'info';
            const toastOptions = {
                delay: options.dismissTime || 5000,
                strong: options.strong
            };

            return showToast(message, toastType, toastOptions);
        } else {
            // Fallback to native alert if toast system not available
            console.warn('Toast system not available, falling back to native alert');
            alert(message);
        }
    } catch (e) {
        console.error("Error showing alert:", e);
        alert(message);
    }
}

// Convenience functions for common alert types - All use unified toast system
function showSuccess(message, options = {}) {
    if (typeof showToast === 'function') {
        return showToast(message, 'success', { strong: 'Success!', ...options });
    }
    return showAlert('success', message, { strong: 'Success!', ...options });
}

function showError(message, options = {}) {
    if (typeof showToast === 'function') {
        return showToast(message, 'error', { strong: 'Error!', ...options });
    }
    return showAlert('danger', message, { strong: 'Error!', ...options });
}

function showWarning(message, options = {}) {
    if (typeof showToast === 'function') {
        return showToast(message, 'warning', { strong: 'Warning!', ...options });
    }
    return showAlert('warning', message, { strong: 'Warning!', ...options });
}

function showInfo(message, options = {}) {
    if (typeof showToast === 'function') {
        return showToast(message, 'info', { strong: 'Info:', ...options });
    }
    return showAlert('info', message, { strong: 'Info:', ...options });
}

// Confirmation dialog using Bootstrap Modal
function showConfirmation(options = {}) {
    const defaults = {
        title: 'Confirm Action',
        message: 'Are you sure you want to proceed?',
        confirmText: 'Confirm',
        cancelText: 'Cancel',
        confirmClass: 'btn-danger',
        onConfirm: () => {},
        onCancel: () => {}
    };

    const config = { ...defaults, ...options };

    // Create modal HTML
    const modalId = 'confirmationModal_' + Date.now();
    const modalHtml = `
        <div class="modal fade" id="${modalId}" tabindex="-1" aria-hidden="true">
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">${config.title}</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body">
                        ${config.message}
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">${config.cancelText}</button>
                        <button type="button" class="btn ${config.confirmClass}" id="${modalId}_confirm">${config.confirmText}</button>
                    </div>
                </div>
            </div>
        </div>
    `;

    // Add modal to DOM
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    const modalElement = document.getElementById(modalId);
    const modal = new bootstrap.Modal(modalElement);

    // Handle confirm button
    document.getElementById(`${modalId}_confirm`).addEventListener('click', () => {
        modal.hide();
        config.onConfirm();
    });

    // Handle cancel (including X button and backdrop)
    modalElement.addEventListener('hidden.bs.modal', () => {
        config.onCancel();
        modalElement.remove(); // Clean up DOM
    });

    // Show modal
    modal.show();

    return modal;
}



// Document ready function
document.addEventListener('DOMContentLoaded', function() {
    try {
        // Initialize dark mode first
        initDarkMode();
        
        // Initialize Bootstrap components
        initTooltips();
        initPopovers();
        
        // Format dates
        formatDateFields();
        
        // Setup Ajax forms
        setupAjaxForms();

    } catch (e) {
        console.error("Error in document ready:", e);
    }
});