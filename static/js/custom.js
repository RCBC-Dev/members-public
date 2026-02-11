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



document.addEventListener("DOMContentLoaded", function () {
    // Dropzone.autoDiscover = false; // Now set globally in base.html before dropzone.js loads

    const getEl = (id) => document.getElementById(id);

    function toggleVisibility(elementWrapper, show) {
        if (elementWrapper) {
            if (show) {
                elementWrapper.classList.remove('d-none');
            } else {
                elementWrapper.classList.add('d-none');
            }
        }
    }

    function toggleRequired(elementInput, required) {
        if (elementInput) {
            elementInput.required = required;
        }
    }

    // --- Print Page Button Logic ---
    const printButton = getEl('print-page-button');
    if (printButton) {
        printButton.addEventListener('click', function() {
            window.print();
        });
    }

    // Helper function to get CSRF token
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    // CSRF token helper for AJAX requests

    // --- Shared Date Range Functionality ---
    window.initializeDateRangeFilters = function(options = {}) {
        const {
            dateRangeSelectId = 'date_range',
            dateFromFieldId = 'date_from',
            dateToFieldId = 'date_to',
            formId = 'filterForm',
            additionalSelectors = [], // Array of additional element IDs that should trigger form submission
            serverDates = null, // Optional server-provided dates for consistency
            customSubmitFunction = null // Optional custom submit function
        } = options;

        let todayStr, date3monthsStr, date6monthsStr, date12monthsStr;

        if (serverDates) {
            // Use server-provided dates for consistency
            todayStr = serverDates.today;
            date3monthsStr = serverDates['3months'].from;
            date6monthsStr = serverDates['6months'].from;
            date12monthsStr = serverDates['12months'].from;
        } else {
            // Fallback to client-side calculation (for backward compatibility)
            const today = new Date();
            const date3months = new Date(today.getFullYear(), today.getMonth() - 3, today.getDate());
            const date6months = new Date(today.getFullYear(), today.getMonth() - 6, today.getDate());
            const date12months = new Date(today.getFullYear(), today.getMonth() - 12, today.getDate());

            todayStr = today.toISOString().split('T')[0];
            date3monthsStr = date3months.toISOString().split('T')[0];
            date6monthsStr = date6months.toISOString().split('T')[0];
            date12monthsStr = date12months.toISOString().split('T')[0];
        }

        const dateRangeSelect = document.getElementById(dateRangeSelectId);
        const dateFromField = document.getElementById(dateFromFieldId);
        const dateToField = document.getElementById(dateToFieldId);
        const form = document.getElementById(formId);

        if (!dateRangeSelect || !dateFromField || !dateToField || !form) {
            console.warn('Date range filter elements not found');
            return;
        }


        // Track whether we're programmatically updating fields
        let isProgrammaticUpdate = false;

        // Function to detect which preset range matches current dates (only for manual changes)
        function detectDateRange() {
            // Only detect when user manually changes dates, not when we update them programmatically
            if (isProgrammaticUpdate) {
                return;
            }

            const fromVal = dateFromField.value;
            const toVal = dateToField.value;

            if (fromVal === date3monthsStr && toVal === todayStr) {
                dateRangeSelect.value = '3months';
            } else if (fromVal === date6monthsStr && toVal === todayStr) {
                dateRangeSelect.value = '6months';
            } else if (fromVal === date12monthsStr && toVal === todayStr) {
                dateRangeSelect.value = '12months';
            } else if (fromVal === '' && toVal === '') {
                dateRangeSelect.value = 'all';
            } else if (fromVal || toVal) {
                // Only change to custom if this is a manual change
                dateRangeSelect.value = 'custom';
            }
        }

        // Function to update date fields based on selected range
        function updateDateFields() {
            const range = dateRangeSelect.value;

            // Set flag to indicate programmatic update
            isProgrammaticUpdate = true;

            if (range === '3months') {
                dateFromField.value = date3monthsStr;
                dateToField.value = todayStr;
            } else if (range === '6months') {
                dateFromField.value = date6monthsStr;
                dateToField.value = todayStr;
            } else if (range === '12months') {
                dateFromField.value = date12monthsStr;
                dateToField.value = todayStr;
            } else if (range === 'all') {
                dateFromField.value = '';
                dateToField.value = '';
            }
            // For 'custom', don't change the fields - let user set them

            // Clear flag after a delay to ensure all events have processed
            setTimeout(() => {
                isProgrammaticUpdate = false;
            }, 50);
        }

        // Function to submit form
        function submitForm() {
            if (customSubmitFunction && typeof customSubmitFunction === 'function') {
                customSubmitFunction();
            } else {
                // Show loading overlay for page navigation
                showLoadingForQuery("Fetching Data", "Please wait while we load the report");
                form.submit();
            }
        }

        // Event handler for date field changes
        function onDateFieldChange() {
            detectDateRange();
            submitForm();
        }

        // Event listeners for auto-submission
        dateRangeSelect.addEventListener('change', function() {
            updateDateFields();
            submitForm();
        });

        dateFromField.addEventListener('change', onDateFieldChange);
        dateToField.addEventListener('change', onDateFieldChange);

        // Add listeners for additional elements
        additionalSelectors.forEach(id => {
            const element = document.getElementById(id);
            if (element) {
                element.addEventListener('change', submitForm);
            }
        });

        // Don't run detectDateRange on page load - trust the server-side value
    };





});

// --- DataTable Export Utilities ---

/**
 * Formats data for DataTable exports by removing HTML tags, decoding HTML entities, and trimming whitespace.
 * This function extracts clean text content from HTML while preserving all visible text and properly decoding entities.
 *
 * @param {string} data - The raw data from the DataTable cell (may contain HTML and entities)
 * @param {number} row - The row index (unused but provided by DataTables)
 * @param {number} column - The column index (unused but provided by DataTables)
 * @param {HTMLElement} node - The DOM node (unused but provided by DataTables)
 * @returns {string} Clean, trimmed text content without HTML markup and with decoded entities
 *
 * @example
 * // Usage in DataTable export configuration:
 * exportOptions: {
 *     columns: ':visible:not(:last-child)',
 *     format: {
 *         body: formatDataTableExport
 *     }
 * }
 *
 * @example
 * // Input/Output examples:
 * formatDataTableExport('<a href="/link/">Display Text</a>') // Returns: "Display Text"
 * formatDataTableExport('Culture &amp; Tourism') // Returns: "Culture & Tourism"
 * formatDataTableExport('<span>Complex <b>HTML</b> content</span>') // Returns: "Complex HTML content"
 */
function formatDataTableExport(data, row, column, node) {
    // Extract text content from HTML, removing tags and decoding HTML entities
    var textContent = data;

    if (typeof data === 'string') {
        // Always create a temporary div to handle both HTML tags and HTML entities
        var tempDiv = document.createElement('div');
        tempDiv.innerHTML = data;
        textContent = tempDiv.textContent || tempDiv.innerText || data;
    }

    // Trim whitespace from the result
    textContent = textContent ? textContent.trim() : textContent;

    return textContent;
}

/**
 * Formats data for DataTable exports with date conversion support.
 * This function removes HTML tags, trims whitespace, and converts dates from YYYY-MM-DD to DD/MM/YYYY format.
 *
 * @param {string} data - The raw data from the DataTable cell (may contain HTML)
 * @param {number} row - The row index (unused but provided by DataTables)
 * @param {number} column - The column index (used for date column detection)
 * @param {HTMLElement} node - The DOM node (unused but provided by DataTables)
 * @param {number[]} dateColumns - Array of column indices that contain dates (e.g., [8, 9])
 * @returns {string} Clean, trimmed text content with dates formatted as DD/MM/YYYY
 *
 * @example
 * // Usage in DataTable export configuration:
 * exportOptions: {
 *     columns: ':visible:not(:last-child)',
 *     format: {
 *         body: function(data, row, column, node) {
 *             return formatDataTableExportWithDates(data, row, column, node, [8, 9]);
 *         }
 *     }
 * }
 *
 * @example
 * // Input/Output examples:
 * formatDataTableExportWithDates('2025-07-09', 0, 8, null, [8, 9]) // Returns: "09/07/2025"
 * formatDataTableExportWithDates('<a href="/link/">2025-07-09</a>', 0, 8, null, [8, 9]) // Returns: "09/07/2025"
 * formatDataTableExportWithDates('Regular text', 0, 0, null, [8, 9]) // Returns: "Regular text"
 */
function formatDataTableExportWithDates(data, row, column, node, dateColumns) {
    // First apply standard HTML removal and trimming
    var textContent = formatDataTableExport(data, row, column, node);

    // Convert dates from YYYY-MM-DD to DD/MM/YYYY for specified columns
    if (dateColumns && dateColumns.includes(column)) {
        var dateMatch = textContent.match(/(\d{4})-(\d{2})-(\d{2})/);
        if (dateMatch) {
            return dateMatch[3] + '/' + dateMatch[2] + '/' + dateMatch[1];
        }
    }

    return textContent;
}

// ===== IMAGE MANAGEMENT UTILITIES =====
// These functions are used by the enquiry form for managing image attachments

/**
 * Create HTML for an image item in the photo dropzone
 * @param {Object} attachment - Image attachment data
 * @param {number} index - Index in the array
 * @param {string} type - 'extracted' or 'manual'
 * @returns {string} HTML string
 */
/**
 * Get the appropriate icon or preview for a file attachment
 * @param {Object} attachment - Attachment data
 * @returns {string} - HTML for file preview/icon
 */
function getFilePreview(attachment) {
    const fileType = attachment.file_type || 'image';
    const filename = attachment.original_filename || '';
    const fileExtension = filename.split('.').pop().toLowerCase();

    if (fileType === 'image') {
        return `<img src="${attachment.file_url}" alt="${filename}" class="img-thumbnail mb-2 img-preview-large">`;
    } else if (fileType === 'document' || ['pdf', 'doc', 'docx'].includes(fileExtension)) {
        if (fileExtension === 'pdf') {
            return `<img src="/static/img/pdf-icon.svg" alt="PDF Document" class="mb-2 doc-icon-100">`;
        } else if (['doc', 'docx'].includes(fileExtension)) {
            return `<img src="/static/img/word-icon.svg" alt="Word Document" class="mb-2 doc-icon-100">`;
        }
    }

    // Fallback for unknown file types
    return `<div class="doc-icon-fallback">
                <i class="bi bi-file-earmark"></i>
            </div>`;
}

function createImageHTML(attachment, index, type) {
    const resizeInfo = attachment.was_resized ?
        `<small class="text-danger d-block"><i class="bi bi-arrow-down-circle"></i> Resized from ${(attachment.original_size / (1024 * 1024)).toFixed(1)} MB</small>` : '';

    const filePreview = getFilePreview(attachment);
    const fileType = attachment.file_type || 'image';
    const removeTitle = fileType === 'image' ? 'Remove this image' : 'Remove this file';

    return `
        <div class="image-item mb-3 p-3 border rounded position-relative" data-image-index="${index}" data-image-type="${type}">
            <div class="text-center">
                ${filePreview}
                <div class="image-info">
                    <div class="fw-bold small attachment-filename" title="${attachment.original_filename}">${attachment.original_filename}</div>
                    <small class="text-muted d-block mt-1">${(attachment.file_size / (1024 * 1024)).toFixed(1)} MB</small>
                    ${resizeInfo}
                </div>
                <button type="button" class="btn btn-sm btn-outline-danger remove-image-btn position-absolute top-0 end-0 m-2"
                        data-image-index="${index}" data-image-type="${type}" title="${removeTitle}">
                    <i class="bi bi-x-circle"></i>
                </button>
            </div>
        </div>
    `;
}

/**
 * Add event listeners for remove image buttons
 * @param {Function} removeCallback - Function to call when remove button is clicked
 */
function addRemoveImageListeners(removeCallback) {
    const removeButtons = document.querySelectorAll('.remove-image-btn');
    removeButtons.forEach(button => {
        button.addEventListener('click', function() {
            const imageIndex = parseInt(this.getAttribute('data-image-index'));
            const imageType = this.getAttribute('data-image-type');
            if (removeCallback) {
                removeCallback(imageIndex, imageType);
            }
        });
    });
}

/**
 * Update photo status message
 * @param {string} message - Status message
 * @param {string} type - 'success', 'error', 'processing', 'warning', or 'default'
 */
function updatePhotoStatus(message, type) {
    const statusElement = document.getElementById('photo-status');
    if (statusElement) {
        statusElement.textContent = message;

        // Remove existing status classes
        statusElement.classList.remove('text-success', 'text-danger', 'text-warning', 'text-info', 'text-muted');

        // Add appropriate class based on type
        switch(type) {
            case 'success':
                statusElement.classList.add('text-success');
                break;
            case 'error':
                statusElement.classList.add('text-danger');
                break;
            case 'processing':
                statusElement.classList.add('text-info');
                break;
            case 'warning':
                statusElement.classList.add('text-warning');
                break;
            default:
                statusElement.classList.add('text-muted');
        }
    }
}

/**
 * Clear the photo dropzone and restore default message
 */
function clearPhotoDropzone() {
    const photoDropzone = document.getElementById('photo-dropzone');
    if (!photoDropzone) return;

    // Restore original dropzone content
    photoDropzone.innerHTML = `
        <div class="dz-message text-center">
            <i class="bi bi-file-earmark fs-3 text-muted"></i>
            <p class="mt-1 mb-1 small">Drop files here or click to browse</p>
            <small class="text-muted">Images, PDFs, Word documents</small>
        </div>
    `;
}

// ===== GLOBAL LOADING OVERLAY FUNCTIONS =====

/**
 * Show the global loading overlay with optional custom messages
 * @param {string} title - Optional custom title (defaults to "Loading...")
 * @param {string} message - Optional custom message (defaults to "Please wait while we process your request")
 */
function showLoadingOverlay(title = null, message = null) {
    const overlay = document.getElementById('loadingOverlay');
    if (overlay) {
        // Update messages if provided
        if (title) {
            const titleElement = overlay.querySelector('h5');
            if (titleElement) titleElement.textContent = title;
        }
        if (message) {
            const messageElement = overlay.querySelector('p.text-muted');
            if (messageElement) messageElement.textContent = message;
        }

        overlay.classList.add('show');
    }
}

/**
 * Hide the global loading overlay
 */
function hideLoadingOverlay() {
    const overlay = document.getElementById('loadingOverlay');
    if (overlay) {
        overlay.classList.remove('show');
    }
}

/**
 * Show loading overlay during a form submission or navigation
 * @param {string} title - Optional custom title
 * @param {string} message - Optional custom message
 */
function showLoadingForSubmission(title = "Processing...", message = "Please wait while we save your changes") {
    // Set navigation flag to track that we're intentionally navigating
    sessionStorage.setItem('intentionalNavigation', 'true');
    showLoadingOverlay(title, message);
}

/**
 * Show loading overlay for database-heavy operations
 * @param {string} title - Optional custom title
 * @param {string} message - Optional custom message
 */
function showLoadingForQuery(title = "Loading data...", message = "Please wait while we fetch your data") {
    showLoadingOverlay(title, message);
}

/**
 * Update the loading overlay message without hiding/showing it
 * @param {string} title - New title
 * @param {string} message - New message
 */
function updateLoadingMessage(title, message) {
    const overlay = document.getElementById('loadingOverlay');
    if (overlay && overlay.classList.contains('show')) {
        if (title) {
            const titleElement = overlay.querySelector('h5');
            if (titleElement) titleElement.textContent = title;
        }
        if (message) {
            const messageElement = overlay.querySelector('p');
            if (messageElement) messageElement.textContent = message;
        }
    }
}

/**
 * Initialize loading overlay handlers for common scenarios
 */
function initializeLoadingOverlay() {
    // Hide overlay on page load if not explicitly shown by server
    const overlay = document.getElementById('loadingOverlay');
    if (overlay && !overlay.classList.contains('show')) {
        hideLoadingOverlay();
    }

    // Clear navigation flags on page load
    sessionStorage.removeItem('intentionalNavigation');

    // Handle pageshow event (fires when page is shown, including from cache)
    window.addEventListener('pageshow', function(event) {
        // Always hide overlay when page is shown from cache (back/forward navigation)
        if (event.persisted) {
            // Page was loaded from bfcache (back/forward button)
            hideLoadingOverlay();
            sessionStorage.removeItem('intentionalNavigation');
        } else if (sessionStorage.getItem('intentionalNavigation') === 'true') {
            // Normal navigation that we initiated
            hideLoadingOverlay();
            sessionStorage.removeItem('intentionalNavigation');
        }
    });

    // Additional safety net using visibility API
    document.addEventListener('visibilitychange', function() {
        if (!document.hidden) {
            // Page became visible - always hide overlay as a safety net
            hideLoadingOverlay();
            sessionStorage.removeItem('intentionalNavigation');
        }
    });

    // Force hide overlay on any page load (safety net)
    window.addEventListener('load', function() {
        // Always hide overlay on page load unless explicitly shown by server
        const overlay = document.getElementById('loadingOverlay');
        if (overlay && !overlay.classList.contains('show')) {
            hideLoadingOverlay();
        }
        // Clear any navigation flags
        sessionStorage.removeItem('intentionalNavigation');
    });

    // Additional safety net - hide overlay after a short delay on page load
    setTimeout(function() {
        const overlay = document.getElementById('loadingOverlay');
        if (overlay && !overlay.classList.contains('show')) {
            hideLoadingOverlay();
        }
    }, 100);

    // Handle browser back/forward button
    window.addEventListener('popstate', function(event) {
        // User clicked back/forward button - hide overlay
        hideLoadingOverlay();
        sessionStorage.removeItem('intentionalNavigation');
    });
}

// Initialize loading overlay on DOM ready
document.addEventListener('DOMContentLoaded', initializeLoadingOverlay);

// --- Image Fallback Handler ---
// Handles broken images by swapping to a fallback src specified in data-fallback-src
document.addEventListener('DOMContentLoaded', function() {
    var fallbackImages = document.querySelectorAll('img[data-fallback-src]');
    fallbackImages.forEach(function(img) {
        img.addEventListener('error', function() {
            var fallbackSrc = this.getAttribute('data-fallback-src');
            if (fallbackSrc && this.src !== fallbackSrc) {
                this.src = fallbackSrc;
            }
        });
    });
});

// Make functions globally available
window.showLoadingOverlay = showLoadingOverlay;
window.hideLoadingOverlay = hideLoadingOverlay;
window.showLoadingForSubmission = showLoadingForSubmission;
window.showLoadingForQuery = showLoadingForQuery;
window.updateLoadingMessage = updateLoadingMessage;

// ===== ENQUIRY FORM FUNCTIONS =====
// Functions moved from enquiry_form.js for consolidation

// Store extracted image attachments for later linking to enquiry (global)
window.extractedImageAttachments = [];
window.manualImageAttachments = [];

/**
 * Get responsive column classes based on number of images
 * @param {number} imageCount - Number of images to display
 * @returns {string} Bootstrap column classes
 */
function getColumnClasses(imageCount) {
    if (imageCount === 1) {
        return 'col-md-6 col-sm-12'; // Single image gets generous space but not too wide
    } else if (imageCount === 2) {
        return 'col-md-6 col-sm-12'; // Two images side by side
    } else if (imageCount >= 3) {
        return 'col-md-4 col-sm-6'; // 3+ images: 3 across on medium screens, 2 on small
    }
}

/**
 * Populate form from email data (global function)
 * @param {Object} emailData - Email data from server
 */
window.populateFormFromEmail = function(emailData) {

    // Populating form with parsed email data

    const titleField = window.titleField || document.getElementById('id_title');
    const descriptionField = window.descriptionField || document.getElementById('id_description');

    if (emailData.subject && titleField) {
        titleField.value = emailData.subject;
    }

    if (emailData.body_content && descriptionField) {
        // Create email metadata header with CSS classes (CSP-friendly)
        let emailMetadata = `
<div class="email-metadata">
    <h6><i class="bi bi-envelope"></i> Original Email Details</h6>
    <p><strong>From:</strong> ${emailData.email_from || 'Unknown'}</p>
    <p><strong>To:</strong> ${emailData.email_to || 'Unknown'}</p>`;

        // Add CC if present
        if (emailData.email_cc && emailData.email_cc.trim()) {
            emailMetadata += `
    <p><strong>CC:</strong> ${emailData.email_cc}</p>`;
        }

        // Add date
        emailMetadata += `
    <p><strong>Date:</strong> ${emailData.email_date || 'Unknown'}</p>
</div>

`;

        // Combine metadata with email content
        const fullContent = emailMetadata + emailData.body_content;

        // Set content in TinyMCE editor
        const editorId = descriptionField.id;
        const editor = tinymce.get(editorId);

        if (editor) {
            // TinyMCE is initialized - set content via TinyMCE API
            // Setting content in TinyMCE editor
            editor.setContent(fullContent);
            editor.fire('change');
        } else {
            // TinyMCE not yet initialized - set textarea value directly
            console.log('TinyMCE not ready, setting textarea value directly');
            descriptionField.value = fullContent;

            // Try again after a short delay in case TinyMCE is still initializing
            setTimeout(() => {
                const retryEditor = tinymce.get(editorId);
                if (retryEditor) {
                    console.log('Retry: Setting content in TinyMCE editor');
                    retryEditor.setContent(fullContent);
                    retryEditor.fire('change');
                }
            }, 1000);
        }
    }

    // Checking if member lookup is available

    if (emailData.sender_email && window.memberSelect) {
        // Attempting automatic member lookup
        // Try to find member by email - call the template function that has Django URL access
        if (typeof window.findMemberByEmail === 'function') {
            window.findMemberByEmail(emailData.sender_email);
        } else {
            // Member lookup function not available
            updateEmailStatus(`Email processed. Please select member manually (${emailData.sender_email})`, 'error');
        }
    } else {
        // Member selection not available
    }

    // Handle image attachments
    if (emailData.image_attachments && emailData.image_attachments.length > 0) {
        window.extractedImageAttachments = emailData.image_attachments;
        window.displayAllImages();
        const totalImages = window.extractedImageAttachments.length + window.manualImageAttachments.length;
        updatePhotoStatus(`${totalImages} image(s) ready`, 'success');

        // Update hidden field with image attachment data
        window.updateAllImagesField();
    } else {
        window.extractedImageAttachments = [];
        window.displayAllImages();
        window.updateAllImagesField();
    }
}

/**
 * Handle AJAX response messages using unified toast system
 */
function handleAjaxResponseMessage(response) {
    if (response && typeof showToast === 'function') {
        if (response.success && response.message) {
            showToast(response.message, response.message_type || 'success');
        } else if (!response.success && response.error) {
            showToast(response.error, response.message_type || 'error');
        }
    }
}

/**
 * Display all images (both extracted and manual) in the photo dropzone area (global)
 */
window.displayAllImages = function() {
    const photoDropzone = document.getElementById('photo-dropzone');
    if (!photoDropzone) return;

    // Clear existing content
    photoDropzone.innerHTML = '';

    const totalImages = window.extractedImageAttachments.length + window.manualImageAttachments.length;

    if (totalImages === 0) {
        // Show default dropzone message
        clearPhotoDropzone();
        return;
    }

    // Create container for all images
    const imageContainer = document.createElement('div');
    imageContainer.className = 'all-images-container';

    // Add extracted images section
    if (window.extractedImageAttachments.length > 0) {
        const extractedSection = document.createElement('div');
        extractedSection.className = 'mb-3';
        extractedSection.innerHTML = '<h6 class="mb-2 text-success"><i class="bi bi-check-circle"></i> Files from Email:</h6>';

        const extractedGrid = document.createElement('div');
        extractedGrid.className = 'row g-2';

        const extractedColumnClasses = getColumnClasses(window.extractedImageAttachments.length);
        window.extractedImageAttachments.forEach((attachment, index) => {
            const imageCol = document.createElement('div');
            imageCol.className = extractedColumnClasses;
            imageCol.innerHTML = window.createImageHTML(attachment, index, 'extracted');
            extractedGrid.appendChild(imageCol);
        });

        extractedSection.appendChild(extractedGrid);
        imageContainer.appendChild(extractedSection);
    }

    // Add manual images section
    if (window.manualImageAttachments.length > 0) {
        const manualSection = document.createElement('div');
        manualSection.className = 'mb-3';
        manualSection.innerHTML = '<h6 class="mb-2 text-primary"><i class="bi bi-cloud-upload"></i> Manually Added Files:</h6>';

        const manualGrid = document.createElement('div');
        manualGrid.className = 'row g-2';

        const manualColumnClasses = getColumnClasses(window.manualImageAttachments.length);
        window.manualImageAttachments.forEach((attachment, index) => {
            const imageCol = document.createElement('div');
            imageCol.className = manualColumnClasses;
            imageCol.innerHTML = window.createImageHTML(attachment, index, 'manual');
            manualGrid.appendChild(imageCol);
        });

        manualSection.appendChild(manualGrid);
        imageContainer.appendChild(manualSection);
    }

    photoDropzone.appendChild(imageContainer);

    // Add event listeners for remove buttons
    window.addRemoveImageListeners(window.removeImage);
}

/**
 * Update hidden field with all image data (extracted + manual) (global)
 */
window.updateAllImagesField = function() {
    const hiddenField = document.getElementById('extracted_images');
    if (hiddenField) {
        // Combine both arrays for form submission
        const allImages = [...window.extractedImageAttachments, ...window.manualImageAttachments];
        hiddenField.value = JSON.stringify(allImages);
    }
}

/**
 * Remove an image from the appropriate list (global)
 */
window.removeImage = function(imageIndex, imageType) {
    let removedImage;

    if (imageType === 'extracted' && imageIndex >= 0 && imageIndex < window.extractedImageAttachments.length) {
        removedImage = window.extractedImageAttachments.splice(imageIndex, 1)[0];
        console.log('Removed extracted image:', removedImage.original_filename);
    } else if (imageType === 'manual' && imageIndex >= 0 && imageIndex < window.manualImageAttachments.length) {
        removedImage = window.manualImageAttachments.splice(imageIndex, 1)[0];
        console.log('Removed manual image:', removedImage.original_filename);
    }

    if (removedImage) {
        // Update the display
        const totalImages = window.extractedImageAttachments.length + window.manualImageAttachments.length;
        if (totalImages > 0) {
            window.displayAllImages();
            updatePhotoStatus(`${totalImages} image(s) ready`, 'success');
        } else {
            clearPhotoDropzone();
            updatePhotoStatus('No photos uploaded', 'default');
        }

        // Update the hidden field
        window.updateAllImagesField();
    }
}

// ===== ENQUIRY FORM SELECTION MANAGER - SIMPLIFIED =====

/**
 * Simple Selection Manager for Enquiry Form
 * Two clear workflows: Contact-First or Job-First
 */
window.EnquirySelectionManager = {
    // DOM elements (set by template)
    elements: {
        jobTypeSelect: null,
        jobTypeSearch: null,
        sectionSelect: null,
        contactSelect: null
    },

    // State tracking
    state: {
        selectionMode: null, // 'job_first' or 'contact_first' or null
        lastJobTypeId: null,
        lastContactId: null
    },

    /**
     * Initialize the selection manager
     */
    init: function(config) {
        // Handle both old and new calling conventions
        if (config.jobTypeSelect) {
            // New config object format
            this.elements = {
                jobTypeSelect: config.jobTypeSelect,
                jobTypeSearch: config.jobTypeSearch,
                sectionSelect: config.sectionSelect,
                contactSelect: config.contactSelect
            };
            this.isEditMode = config.isEditMode || false;
        } else {
            // Old elements object format (backward compatibility)
            this.elements = config;
            this.isEditMode = false;
        }

        this.setupSectionField();
        this.bindEvents();
        this.loadAllContacts(); // Start with all contacts available
        console.log('EnquirySelectionManager initialized, edit mode:', this.isEditMode);
    },

    /**
     * Setup section field as read-only
     */
    setupSectionField: function() {
        if (this.elements.sectionSelect) {
            // Use readonly instead of disabled so the value is submitted
            this.elements.sectionSelect.readOnly = true;
            this.elements.sectionSelect.style.backgroundColor = '#f8f9fa';
            this.elements.sectionSelect.style.pointerEvents = 'none'; // Prevent user interaction

            if (this.isEditMode) {
                // In edit mode, preserve the existing section value
                const currentValue = this.elements.sectionSelect.value;
                const currentText = this.elements.sectionSelect.options[this.elements.sectionSelect.selectedIndex]?.text || '';

                if (currentValue && currentText) {
                    // Keep the existing selected option
                    console.log('Edit mode: Preserving existing section:', currentText);
                } else {
                    // No section selected, show placeholder
                    this.elements.sectionSelect.innerHTML = '<option value="">No section assigned</option>';
                }
            } else {
                // In create mode, show auto-populate message
                this.elements.sectionSelect.innerHTML = '<option value="">Auto-populated from contact</option>';
            }
        }
    },

    /**
     * Reset all selections
     */
    resetSelections: function() {
        console.log('Resetting all selections');

        // Clear state
        this.state.selectionMode = null;
        this.state.lastJobTypeId = null;
        this.state.lastContactId = null;

        // Clear job type search
        if (this.elements.jobTypeSearch) {
            this.elements.jobTypeSearch.value = '';
            this.elements.jobTypeSearch.placeholder = 'Type to search job types (e.g., \'grass\', \'roads\')...';
        }

        // Reset section
        this.setupSectionField();

        // Load all contacts and all job types
        this.loadAllContacts();
        this.loadAllJobTypes();

        console.log('All selections reset');
    },

    /**
     * Bind event listeners
     */
    bindEvents: function() {
        // Job type dropdown change
        if (this.elements.jobTypeSelect) {
            this.elements.jobTypeSelect.addEventListener('change', (e) => {
                this.handleJobTypeChange(e.target.value);
            });
        }

        // Contact dropdown change
        if (this.elements.contactSelect) {
            this.elements.contactSelect.addEventListener('change', (e) => {
                this.handleContactChange(e.target.value);
            });
        }
    },

    /**
     * Handle job type selection from search (called by template)
     */
    onJobTypeSearchSelect: function(jobTypeId, jobTypeName) {
        this.handleJobTypeChange(jobTypeId, jobTypeName);
    },

    /**
     * Handle job type change
     */
    handleJobTypeChange: function(jobTypeId, jobTypeName = null) {
        console.log('Job type changed:', jobTypeId, 'Previous:', this.state.lastJobTypeId);

        if (jobTypeId) {
            // Get job type name if not provided
            if (!jobTypeName && this.elements.jobTypeSelect) {
                const option = this.elements.jobTypeSelect.querySelector(`option[value="${jobTypeId}"]`);
                jobTypeName = option ? option.textContent : '';
            }

            // Update UI
            this.updateJobTypeUI(jobTypeId, jobTypeName);

            // Check if this is a different job type than before
            const jobTypeChanged = this.state.lastJobTypeId !== jobTypeId;

            if (jobTypeChanged) {
                console.log('Job type actually changed, updating state and lists');

                // Only clear contact if we're NOT in contact_first mode
                if (this.state.selectionMode !== 'contact_first') {
                    console.log('Not in contact_first mode, clearing contact and filtering');
                    // Set selection mode to job_first
                    this.state.selectionMode = 'job_first';

                    // Clear contact selection and reset last contact ID
                    this.state.lastContactId = null;
                    if (this.elements.contactSelect) {
                        this.elements.contactSelect.value = '';
                    }

                    // Load contacts for this job type
                    console.log('Loading contacts for new job type');
                    this.loadContactsByJobType(jobTypeId);

                    // Reset section (will be set when contact is selected)
                    this.setupSectionField();
                } else {
                    console.log('In contact_first mode, preserving contact selection');
                }

                this.state.lastJobTypeId = jobTypeId;
            } else {
                console.log('Same job type selected, no change needed');
            }
        } else {
            // Job type cleared
            console.log('Job type cleared, resetting to default state');
            this.state.selectionMode = null;
            this.state.lastJobTypeId = null;
            this.state.lastContactId = null;

            // Load all contacts
            this.loadAllContacts();
            this.setupSectionField();
        }
    },

    /**
     * Handle contact change
     */
    handleContactChange: function(contactId) {
        console.log('Contact changed:', contactId, 'Previous:', this.state.lastContactId);

        if (contactId) {
            // Always update section for this contact
            this.loadContactSection(contactId);

            // Check if this is a different contact than before
            const contactChanged = this.state.lastContactId !== contactId;

            if (contactChanged) {
                console.log('Contact actually changed, updating state and lists');

                // Only clear job type if we're NOT in job_first mode
                if (this.state.selectionMode !== 'job_first') {
                    console.log('Not in job_first mode, clearing job type and filtering');
                    // Set selection mode to contact_first
                    this.state.selectionMode = 'contact_first';

                    // Clear job type selection and reset last job type ID
                    this.state.lastJobTypeId = null;
                    if (this.elements.jobTypeSelect) {
                        this.elements.jobTypeSelect.value = '';
                    }
                    if (this.elements.jobTypeSearch) {
                        this.elements.jobTypeSearch.value = '';
                    }

                    // Load job types for this contact
                    console.log('Loading job types for new contact');
                    this.loadJobTypesByContact(contactId);
                } else {
                    console.log('In job_first mode, preserving job type selection');
                }

                this.state.lastContactId = contactId;
            } else {
                console.log('Same contact selected, no change needed');
            }
        } else {
            // Contact cleared
            console.log('Contact cleared, resetting to default state');
            this.state.selectionMode = null;
            this.state.lastContactId = null;
            this.state.lastJobTypeId = null;

            // Reset section
            this.setupSectionField();
        }
    },

    /**
     * Update job type UI elements
     */
    updateJobTypeUI: function(jobTypeId, jobTypeName) {
        if (this.elements.jobTypeSelect && this.elements.jobTypeSelect.value !== jobTypeId) {
            this.elements.jobTypeSelect.value = jobTypeId;
        }
        if (this.elements.jobTypeSearch && this.elements.jobTypeSearch.value !== jobTypeName) {
            this.elements.jobTypeSearch.value = jobTypeName || '';
        }
    },


    /**
     * Validate that selected job type is compatible with selected contact
     */
    validateJobTypeWithContact: function(contactId, jobTypeId) {
        console.log('Validating job type compatibility:', { contactId, jobTypeId });

        if (window.loadJobTypesByContactAPI) {
            window.loadJobTypesByContactAPI(contactId).then((jobTypes) => {
                console.log('Contact job types:', jobTypes);

                // Check if current job type is in the contact's job types
                const isCompatible = jobTypes.some(jobType => jobType.id == jobTypeId);

                if (isCompatible) {
                    console.log('Job type is compatible with selected contact');
                    // Optionally show a success message
                } else {
                    console.warn('Job type is NOT compatible with selected contact');
                    // Show warning to user but don't clear the selection
                    this.showCompatibilityWarning(jobTypeId, contactId);
                }
            }).catch((error) => {
                console.error('Error validating job type compatibility:', error);
            });
        }
    },

    /**
     * Validate that selected contact can handle the selected job type
     */
    validateContactWithJobType: function(contactId, jobTypeId) {
        console.log('Validating contact compatibility with job type:', { contactId, jobTypeId });

        if (window.loadJobTypesByContactAPI) {
            window.loadJobTypesByContactAPI(contactId).then((jobTypes) => {
                console.log('Contact job types:', jobTypes);

                // Check if current job type is in the contact's job types
                const isCompatible = jobTypes.some(jobType => jobType.id == jobTypeId);

                if (isCompatible) {
                    console.log('Contact can handle the selected job type');
                    // Clear any previous warning
                    if (this.elements.jobTypeSearch) {
                        this.elements.jobTypeSearch.placeholder = 'Type to search job types (e.g., \'grass\', \'roads\')...';
                    }
                } else {
                    console.warn('Contact cannot handle the selected job type');
                    // Show warning to user but don't clear the selection
                    this.showCompatibilityWarning(jobTypeId, contactId);
                }
            }).catch((error) => {
                console.error('Error validating contact compatibility:', error);
            });
        }
    },

    /**
     * Show warning when job type and contact are incompatible
     */
    showCompatibilityWarning: function(jobTypeId, contactId) {
        // Get current job type name
        const jobTypeOption = this.elements.jobTypeSelect.querySelector(`option[value="${jobTypeId}"]`);
        const jobTypeName = jobTypeOption ? jobTypeOption.textContent : 'selected job type';

        // Get current contact name
        const contactOption = this.elements.contactSelect.querySelector(`option[value="${contactId}"]`);
        const contactName = contactOption ? contactOption.textContent : 'selected contact';

        console.warn(`Warning: "${jobTypeName}" may not be handled by "${contactName}"`);

        // Update job type search placeholder to show warning
        if (this.elements.jobTypeSearch) {



            this.elements.jobTypeSearch.placeholder = `⚠️ "${jobTypeName}" may not be handled by this contact`;
        }
    },

    /**
     * Validate current state and show warnings if needed
     */
    validateCurrentState: function() {
        // Check if current selections are compatible
        const jobTypeId = this.elements.jobTypeSelect.value;
        const contactId = this.elements.contactSelect.value;

        if (jobTypeId && contactId) {
            // Verify contact can handle this job type
            this.validateJobTypeWithContact(contactId, jobTypeId);
        }

        console.log('Current state validated');
    },


    // ===== API METHODS =====
    // These methods will be called by the template with Django URLs

    // loadSectionsByJobType removed - sections are only set by contact selection

    /**
     * Load all contacts
     */
    loadAllContacts: function() {
        if (window.loadAllContactsAPI) {
            window.loadAllContactsAPI().then((contacts) => {
                this.populateContactSelect(contacts);
            });
        }
    },

    /**
     * Load all job types
     */
    loadAllJobTypes: function() {
        if (window.loadAllJobTypesAPI) {
            window.loadAllJobTypesAPI().then((jobTypes) => {
                this.populateJobTypeSelect(jobTypes);
            });
        }
    },

    /**
     * Load contacts by job type
     */
    loadContactsByJobType: function(jobTypeId) {
        if (window.loadContactsByJobTypeAPI) {
            window.loadContactsByJobTypeAPI(jobTypeId).then((contacts) => {
                console.log('Loading contacts for job type:', jobTypeId, 'found:', contacts.length);

                // Simply populate the contact select with filtered contacts
                // The contact selection was already cleared in handleJobTypeChange if needed
                this.populateContactSelect(contacts);
            });
        }
    },

    /**
     * Load job types by contact (filter dropdown to only show contact's job types)
     */
    loadJobTypesByContact: function(contactId) {
        console.log('Loading job types for contact:', contactId);
        if (window.loadJobTypesByContactAPI) {
            window.loadJobTypesByContactAPI(contactId).then((jobTypes) => {
                console.log('API returned job types:', jobTypes);

                // Simply filter the job type dropdown to only show contact's job types
                // The job type selection was already cleared in handleContactChange if needed
                this.filterJobTypeSelect(jobTypes);

                // Update search placeholder
                if (this.elements.jobTypeSearch) {
                    if (jobTypes.length === 0) {
                        this.elements.jobTypeSearch.placeholder = 'No job types assigned to this contact';
                    } else {
                        this.elements.jobTypeSearch.placeholder = `Select from ${jobTypes.length} job types for this contact`;
                    }
                }

                console.log(`Job type dropdown filtered to ${jobTypes.length} options for this contact`);
            }).catch((error) => {
                console.error('Error loading job types by contact:', error);
            });
        } else {
            console.error('loadJobTypesByContactAPI not available');
        }
    },

    /**
     * Load contact section
     */
    loadContactSection: function(contactId) {
        if (window.loadContactSectionAPI) {
            window.loadContactSectionAPI(contactId).then((data) => {
                if (data.success && data.section) {
                    this.elements.sectionSelect.innerHTML = `<option value="${data.section.id}">${data.section.name}</option>`;
                    this.elements.sectionSelect.value = data.section.id;
                    // Section updated
                }
            });
        }
    },


    /**
     * Populate contact select
     */
    populateContactSelect: function(contacts) {
        if (!this.elements.contactSelect) return;

        this.elements.contactSelect.innerHTML = '<option value="">---------</option>';
        contacts.forEach(contact => {
            const option = document.createElement('option');
            option.value = contact.id;

            // Display areas instead of telephone number
            let displayText = contact.name;
            if (contact.areas && contact.areas.length > 0) {
                displayText += ` (${contact.areas.join(', ')})`;
            } else {
                displayText += ' (no areas assigned)';
            }

            option.textContent = displayText;
            this.elements.contactSelect.appendChild(option);
        });
    },

    /**
     * Populate job type select with filtered job types
     */
    populateJobTypeSelect: function(jobTypes) {
        console.log('populateJobTypeSelect called with:', jobTypes);
        console.log('this.elements.jobTypeSelect:', this.elements.jobTypeSelect);

        if (!this.elements.jobTypeSelect) {
            console.error('jobTypeSelect element not found!');
            return;
        }



        console.log('Populating job type select with:', jobTypes);

        // Clear current options
        this.elements.jobTypeSelect.innerHTML = '<option value="">---------</option>';

        // Add job types
        jobTypes.forEach(jobType => {
            console.log('Adding job type:', jobType.name);
            const option = document.createElement('option');
            option.value = jobType.id;
            option.textContent = jobType.name;
            this.elements.jobTypeSelect.appendChild(option);
        });

        // Update search placeholder
        if (this.elements.jobTypeSearch) {
            if (jobTypes.length === 0) {
                this.elements.jobTypeSearch.placeholder = 'No job types assigned to this contact';
            } else {
                this.elements.jobTypeSearch.placeholder = `Select from ${jobTypes.length} job types for this contact`;
            }
        }

        console.log(`Job type dropdown updated with ${jobTypes.length} options`);
    },


    /**
     * Filter job type select to only show contact's job types
     */
    filterJobTypeSelect: function(contactJobTypes) {
        if (!this.elements.jobTypeSelect) return;

        // Clear current options except the default
        this.elements.jobTypeSelect.innerHTML = '<option value="">---------</option>';

        // Add only the contact's job types
        contactJobTypes.forEach(jobType => {
            const option = document.createElement('option');
            option.value = jobType.id;
            option.textContent = jobType.name;
            this.elements.jobTypeSelect.appendChild(option);
        });

        console.log(`Job type dropdown filtered to ${contactJobTypes.length} options for this contact`);
    },

    /**
     * Clear job type options when contact has no job types
     */
    clearJobTypeOptions: function() {
        if (!this.elements.jobTypeSelect) return;

        this.elements.jobTypeSelect.innerHTML = '<option value="">---------</option>';

        if (this.elements.jobTypeSearch) {
            this.elements.jobTypeSearch.value = '';
            this.elements.jobTypeSearch.placeholder = 'No job types assigned to this contact';
        }
    }
};

// ===== ENQUIRY ACTIONS (CLOSE/REOPEN) =====
// AJAX functionality for closing and reopening enquiries from list pages

document.addEventListener('DOMContentLoaded', function() {
    console.log('Enquiry actions JavaScript loaded');

    // Helper function to check if we're on a list page (not detail page)
    function isListPage() {
        const path = window.location.pathname;
        return path === '/enquiries/' || path === '/home/' || path === '/';
    }

    // Debounce mechanism to prevent duplicate requests
    const pendingRequests = new Set();

    function isRequestPending(key) {
        return pendingRequests.has(key);
    }

    function addPendingRequest(key) {
        pendingRequests.add(key);
    }

    function removePendingRequest(key) {
        pendingRequests.delete(key);
    }

    // Helper function to ensure modal exists for an enquiry
    function ensureModalExists(enquiryId, modalType) {
        const modalId = `${modalType}EnquiryModal${enquiryId}`;
        let modal = document.getElementById(modalId);

        if (!modal) {
            // Create modal dynamically
            modal = document.createElement('div');
            modal.className = 'modal fade';
            modal.id = modalId;
            modal.setAttribute('tabindex', '-1');
            modal.setAttribute('aria-labelledby', `${modalType}EnquiryModalLabel${enquiryId}`);
            modal.setAttribute('aria-hidden', 'true');

            if (modalType === 'close') {
                modal.innerHTML = `
                    <div class="modal-dialog">
                        <div class="modal-content">
                            <div class="modal-header">
                                <h5 class="modal-title" id="closeEnquiryModalLabel${enquiryId}">
                                    <i class="bi bi-exclamation-triangle text-warning me-2"></i>Close Enquiry
                                </h5>
                                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                            </div>
                            <div class="modal-body">
                                <p>Are you sure you want to close this enquiry?</p>
                                <p class="text-muted mb-0">This will mark the enquiry as resolved. You can still view the enquiry details, but it will be considered complete.</p>
                            </div>
                            <div class="modal-footer">
                                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                                <button type="button" class="btn btn-danger close-enquiry-btn" data-enquiry-id="${enquiryId}">
                                    <i class="bi bi-x-circle me-1"></i>Close Enquiry
                                </button>
                            </div>
                        </div>
                    </div>
                `;
            } else if (modalType === 'reopen') {
                modal.innerHTML = `
                    <div class="modal-dialog">
                        <div class="modal-content">
                            <div class="modal-header">
                                <h5 class="modal-title" id="reopenEnquiryModalLabel${enquiryId}">
                                    <i class="bi bi-arrow-clockwise text-success me-2"></i>Re-Open Enquiry
                                </h5>
                                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                            </div>
                            <div class="modal-body">
                                <p>Please select a reason for re-opening this enquiry:</p>
                                <div class="mb-3">
                                    <label for="reopenReason${enquiryId}" class="form-label">Reason <span class="text-danger">*</span></label>
                                    <select class="form-select" id="reopenReason${enquiryId}" required>
                                        <option value="">Select a reason...</option>
                                        <option value="additional_information">Additional information received</option>
                                        <option value="member_request">Member requested follow-up</option>
                                        <option value="incomplete_resolution">Resolution was incomplete</option>
                                        <option value="new_development">New development in the matter</option>
                                        <option value="error_closure">Enquiry was closed in error</option>
                                        <option value="other">Other</option>
                                    </select>
                                </div>
                                <div class="mb-3">
                                    <label for="reopenNote${enquiryId}" class="form-label">Additional Notes</label>
                                    <textarea class="form-control" id="reopenNote${enquiryId}" rows="3" placeholder="Optional additional details..."></textarea>
                                </div>
                            </div>
                            <div class="modal-footer">
                                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                                <button type="button" class="btn btn-success reopen-enquiry-btn" data-enquiry-id="${enquiryId}" disabled>
                                    <i class="bi bi-arrow-clockwise me-1"></i>Re-Open Enquiry
                                </button>
                            </div>
                        </div>
                    </div>
                `;
            }

            document.body.appendChild(modal);
        }

        return modal;
    }

    // Helper function to update enquiry row in list
    function updateEnquiryRow(enquiryId, enquiryData) {
        const row = document.querySelector(`tr[data-enquiry-id="${enquiryId}"]`);
        if (!row) return;

        // Update status badge
        const statusCell = row.querySelector('.status-badge, .badge');
        if (statusCell) {
            statusCell.className = enquiryData.status === 'closed' ? 'badge bg-success' : 'badge bg-primary';
            statusCell.textContent = enquiryData.status === 'new' ? 'Open' : enquiryData.status_display;
        }

        // Update Closed column (if it exists - only in enquiry list, not dashboard)
        const cells = row.querySelectorAll('td');
        if (cells.length > 10) { // Enquiry list has 13 columns, dashboard has fewer
            // Find the Closed column (index 10: Ref, Title, Member, Section, Job Type, Contact, Status, Admin, Created, Due Date, Closed, Resolution Time, Actions)
            const closedCell = cells[10];
            if (closedCell && enquiryData.closed_at_formatted !== undefined) {
                closedCell.textContent = enquiryData.closed_at_formatted;
            }

            // Find the Resolution Time column (index 11)
            const resolutionCell = cells[11];
            if (resolutionCell && enquiryData.resolution_time) {
                if (enquiryData.resolution_time.display === '-') {
                    resolutionCell.innerHTML = '<span class="text-muted">-</span>';
                } else {
                    resolutionCell.innerHTML = `<span class="${enquiryData.resolution_time.color_class}">${enquiryData.resolution_time.display}</span>`;
                }
            }
        }

        // Update action buttons - swap close/reopen buttons and handle Edit button
        const actionCell = row.querySelector('.btn-group');
        if (actionCell) {
            const editBtn = actionCell.querySelector('a[href*="/edit"]');
            const closeBtn = actionCell.querySelector('[data-bs-target*="closeEnquiry"]');
            const reopenBtn = actionCell.querySelector('[data-bs-target*="reopenEnquiry"]');

            if (enquiryData.status === 'closed') {
                // Hide Edit and Close buttons, show Reopen button
                if (editBtn) editBtn.style.display = 'none';
                if (closeBtn) closeBtn.style.display = 'none';
                if (reopenBtn) {
                    reopenBtn.style.display = 'inline-block';
                } else {
                    // Ensure reopen modal exists
                    ensureModalExists(enquiryData.id, 'reopen');

                    // Create reopen button if it doesn't exist
                    const newReopenBtn = document.createElement('button');
                    newReopenBtn.type = 'button';
                    newReopenBtn.className = 'btn btn-outline-success';
                    newReopenBtn.setAttribute('data-bs-toggle', 'modal');
                    newReopenBtn.setAttribute('data-bs-target', `#reopenEnquiryModal${enquiryData.id}`);
                    newReopenBtn.title = 'Re-open this enquiry';
                    newReopenBtn.innerHTML = '<i class="bi bi-arrow-clockwise"></i> Re-open';
                    actionCell.appendChild(newReopenBtn);
                }
            } else {
                // Show Edit and Close buttons, hide Reopen button
                if (editBtn) {
                    editBtn.style.display = 'inline-block';
                } else {
                    // Create Edit button if it doesn't exist
                    const newEditBtn = document.createElement('a');
                    newEditBtn.href = `/enquiries/${enquiryData.id}/edit/`;
                    newEditBtn.className = 'btn btn-outline-secondary';
                    newEditBtn.title = 'Edit this enquiry';
                    newEditBtn.innerHTML = '<i class="bi bi-pencil"></i> Edit';
                    actionCell.appendChild(newEditBtn);
                }

                if (reopenBtn) reopenBtn.style.display = 'none';
                if (closeBtn) {
                    closeBtn.style.display = 'inline-block';
                } else {
                    // Ensure close modal exists
                    ensureModalExists(enquiryData.id, 'close');

                    // Create close button if it doesn't exist
                    const newCloseBtn = document.createElement('button');
                    newCloseBtn.type = 'button';
                    newCloseBtn.className = 'btn btn-outline-danger';
                    newCloseBtn.setAttribute('data-bs-toggle', 'modal');
                    newCloseBtn.setAttribute('data-bs-target', `#closeEnquiryModal${enquiryData.id}`);
                    newCloseBtn.title = 'Close this enquiry';
                    newCloseBtn.innerHTML = '<i class="bi bi-x-circle"></i> Close';
                    actionCell.appendChild(newCloseBtn);
                }
            }
        }
    }

    // Note: showToast is now available globally from base.html

    // Handle close enquiry button clicks using event delegation
    document.addEventListener('click', function(e) {
        if (e.target.closest('.close-enquiry-btn')) {
            const button = e.target.closest('.close-enquiry-btn');
            const enquiryId = button.getAttribute('data-enquiry-id');
            const requestKey = `close-${enquiryId}`;

            // Prevent duplicate requests
            if (isRequestPending(requestKey)) {
                console.log('Close request already pending for enquiry', enquiryId);
                return;
            }

            // Hide modal
            const closeModal = bootstrap.Modal.getInstance(document.getElementById('closeEnquiryModal' + enquiryId));
            if (closeModal) closeModal.hide();

            // Show loading state
            const originalText = button.innerHTML;
            button.disabled = true;
            button.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>Closing...';

            // Add to pending requests
            addPendingRequest(requestKey);
            console.log('Starting close request for enquiry', enquiryId);

            // If on list page, use AJAX
            if (isListPage()) {
                fetch(`/enquiries/${enquiryId}/close/`, {
                    method: 'POST',
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
                        'Content-Type': 'application/x-www-form-urlencoded',
                    }
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        updateEnquiryRow(enquiryId, data.enquiry);
                        showToast(data.message, 'success');
                    } else {
                        showToast(data.message, 'error');
                    }
                })
                .catch(error => {
                    console.error('Close enquiry error:', error);
                    showToast('An error occurred while closing the enquiry.', 'error');
                })
                .finally(() => {
                    // Reset button state
                    button.disabled = false;
                    button.innerHTML = originalText;
                    // Remove from pending requests
                    removePendingRequest(requestKey);
                    console.log('Completed close request for enquiry', enquiryId);
                });
            } else {
                // Submit the form (for detail page)
                document.getElementById('closeEnquiryForm' + enquiryId).submit();
                // Remove from pending requests since we're navigating away
                removePendingRequest(requestKey);
            }
        }
    });

    // Handle reopen enquiry button clicks using event delegation
    document.addEventListener('click', function(e) {
        if (e.target.closest('.reopen-enquiry-btn')) {
            const button = e.target.closest('.reopen-enquiry-btn');
            const enquiryId = button.getAttribute('data-enquiry-id');
            const requestKey = `reopen-${enquiryId}`;

            // Prevent duplicate requests
            if (isRequestPending(requestKey)) {
                console.log('Reopen request already pending for enquiry', enquiryId);
                return;
            }

            const reason = document.getElementById('reopenReason' + enquiryId).value;
            const note = document.getElementById('reopenNote' + enquiryId).value.trim();

            if (!reason) {
                // Use global toast notification system instead of alert
                if (typeof showToast === 'function') {
                    showToast('Please select a reason for re-opening the enquiry.', 'warning');
                } else {
                    console.warn('showToast function not available, falling back to alert');
                    alert('Please select a reason for re-opening the enquiry.');
                }
                return;
            }

            // Hide modal
            const reopenModal = bootstrap.Modal.getInstance(document.getElementById('reopenEnquiryModal' + enquiryId));
            if (reopenModal) reopenModal.hide();

            // Show loading state
            const originalText = button.innerHTML;
            button.disabled = true;
            button.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>Re-opening...';

            // Add to pending requests
            addPendingRequest(requestKey);
            console.log('Starting reopen request for enquiry', enquiryId);

            // If on list page, use AJAX
            if (isListPage()) {
                const formData = new FormData();
                formData.append('reason', reason);
                formData.append('note', note);
                formData.append('csrfmiddlewaretoken', document.querySelector('[name=csrfmiddlewaretoken]').value);

                fetch(`/enquiries/${enquiryId}/reopen/`, {
                    method: 'POST',
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                    },
                    body: formData
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        updateEnquiryRow(enquiryId, data.enquiry);
                        showToast(data.message, 'success');
                        // Reset form
                        document.getElementById('reopenReason' + enquiryId).value = '';
                        document.getElementById('reopenNote' + enquiryId).value = '';
                    } else {
                        showToast(data.message, 'error');
                    }
                })
                .catch(error => {
                    console.error('Reopen enquiry error:', error);
                    showToast('An error occurred while re-opening the enquiry.', 'error');
                })
                .finally(() => {
                    // Reset button state
                    button.disabled = false;
                    button.innerHTML = originalText;
                    // Remove from pending requests
                    removePendingRequest(requestKey);
                    console.log('Completed reopen request for enquiry', enquiryId);
                });
            } else {
                // Set hidden form values and submit the form (for detail page)
                document.getElementById('hiddenReopenReason' + enquiryId).value = reason;
                document.getElementById('hiddenReopenNote' + enquiryId).value = note;
                document.getElementById('reopenEnquiryForm' + enquiryId).submit();
                // Remove from pending requests since we're navigating away
                removePendingRequest(requestKey);
            }
        }
    });

    // Handle reopen reason validation using event delegation
    document.addEventListener('change', function(e) {
        if (e.target.matches('[id^="reopenReason"]')) {
            const select = e.target;
            const enquiryId = select.id.replace('reopenReason', '');

            // Try both possible button IDs (static and dynamic modals)
            let confirmButton = document.getElementById('confirmReopenEnquiry' + enquiryId);
            if (!confirmButton) {
                // For dynamically created modals, the button class is 'reopen-enquiry-btn'
                const modal = document.getElementById('reopenEnquiryModal' + enquiryId);
                if (modal) {
                    confirmButton = modal.querySelector('.reopen-enquiry-btn');
                }
            }

            if (confirmButton) {
                confirmButton.disabled = !select.value;
            }
        }
    });

    // ===== EMAIL DROPZONE FOR HISTORY FORM =====
    // Initialize email dropzone functionality for history notes
    const emailDropzone = document.getElementById('email-update-dropzone');
    if (emailDropzone) {
        const dropzoneContent = emailDropzone.querySelector('.dropzone-content');
        const dropzoneLoading = emailDropzone.querySelector('.dropzone-loading');

        if (dropzoneContent && dropzoneLoading) {
            // Dropzone event handlers
            emailDropzone.addEventListener('dragover', function(e) {
                e.preventDefault();
                emailDropzone.classList.add('border-success', 'bg-light');
            });

            emailDropzone.addEventListener('dragleave', function(e) {
                e.preventDefault();
                emailDropzone.classList.remove('border-success', 'bg-light');
            });

            emailDropzone.addEventListener('drop', function(e) {
                e.preventDefault();
                emailDropzone.classList.remove('border-success', 'bg-light');

                const files = e.dataTransfer.files;
                if (files.length > 0) {
                    processEmailFileForHistory(files[0]);
                }
            });

            // Process email file for history
            function processEmailFileForHistory(file) {
                // Check file type
                const allowedTypes = ['.msg', '.eml'];
                const fileExtension = '.' + file.name.split('.').pop().toLowerCase();

                if (!allowedTypes.includes(fileExtension)) {
                    showError('Please upload only .msg or .eml files.');
                    return;
                }

                // Show loading state
                dropzoneContent.classList.add('d-none');
                dropzoneLoading.classList.remove('d-none');

                // Create FormData
                const formData = new FormData();
                formData.append('email_file', file);

                // Send to email parsing API for history
                fetch('/api/parse-email-update/', {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                    },
                    body: formData
                })
                .then(response => response.json())
                .then(data => {

                    if (data.success) {
                        populateHistoryFormWithEmail(data.email_data);
                        showSuccess('Email processed successfully - content loaded into note form');
                    } else {
                        showError('Error processing email: ' + (data.error || 'Unknown error'));
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    showError('Error processing email: ' + error.message);
                })
                .finally(() => {
                    // Reset dropzone
                    dropzoneContent.classList.remove('d-none');
                    dropzoneLoading.classList.add('d-none');
                });
            }

            // Populate history form with email content
            function populateHistoryFormWithEmail(emailData) {
                // Auto-set note type based on email direction
                const noteTypeSelect = document.querySelector('#id_note_type');
                if (noteTypeSelect) {
                    const direction = emailData.direction || 'UNKNOWN';
                    if (direction === 'INCOMING') {
                        noteTypeSelect.value = 'email_incoming';
                    } else if (direction === 'OUTGOING') {
                        noteTypeSelect.value = 'email_outgoing';
                    } else {
                        noteTypeSelect.value = 'general';
                    }
                }

                // Create formatted note content with proper line breaks
                let noteContent = `Subject: ${emailData.subject || 'No subject'}\n\n`;
                noteContent += `From: ${emailData.from || 'Unknown sender'}\n`;
                if (emailData.to) {
                    noteContent += `To: ${emailData.to}\n`;
                }
                if (emailData.cc) {
                    noteContent += `CC: ${emailData.cc}\n`;
                }
                noteContent += `Date: ${emailData.date || 'Unknown date'}\n\n`;
                noteContent += emailData.body || '';

                // Set content in note field
                const noteField = document.querySelector('#id_note');
                if (noteField) {
                    noteField.value = noteContent;
                }
            }
        }
    }
});
