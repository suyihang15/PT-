/**
 * BT种子管理系统 - Main JavaScript
 */

// Dismiss flash alerts after 5 seconds
document.addEventListener('DOMContentLoaded', function() {
    const alerts = document.querySelectorAll('.alert-dismissible');
    alerts.forEach(function(alert) {
        setTimeout(function() {
            const closeBtn = alert.querySelector('.btn-close');
            if (closeBtn) {
                closeBtn.click();
            }
        }, 5000);
    });

    // Initialize global search autocomplete
    initSearchAutocomplete();

    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Initialize popovers
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
});

// ===== CSRF Setup for AJAX =====
function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (meta) return meta.getAttribute('content');
    // Look for CSRF token in hidden input
    const input = document.querySelector('input[name="csrf_token"]');
    if (input) return input.value;
    return '';
}

// ===== AJAX Helper =====
function ajaxPost(url, data, successCallback, errorCallback) {
    const csrf = getCsrfToken();
    const headers = {
        'Content-Type': 'application/json',
    };
    if (csrf) {
        headers['X-CSRFToken'] = csrf;
    }

    fetch(url, {
        method: 'POST',
        headers: headers,
        body: JSON.stringify(data),
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Network response was not ok: ' + response.status);
        }
        return response.json();
    })
    .then(data => {
        if (successCallback) successCallback(data);
    })
    .catch(error => {
        if (errorCallback) errorCallback(error);
        else console.error('AJAX Error:', error);
    });
}

// ===== Search Autocomplete =====
let searchTimeout = null;

function initSearchAutocomplete() {
    const searchInput = document.getElementById('global-search-input');
    const suggestionsBox = document.getElementById('search-suggestions');

    if (!searchInput || !suggestionsBox) return;

    searchInput.addEventListener('input', function() {
        const query = this.value.trim();
        clearTimeout(searchTimeout);

        if (query.length < 2) {
            suggestionsBox.style.display = 'none';
            return;
        }

        searchTimeout = setTimeout(function() {
            fetch('/api/search/autocomplete?q=' + encodeURIComponent(query))
                .then(r => r.json())
                .then(data => {
                    if (data.results && data.results.length > 0) {
                        suggestionsBox.innerHTML = data.results.map(function(item) {
                            return `<a href="/torrent/${item.id}" class="dropdown-item small">
                                ${item.name}
                                <span class="text-muted float-end">${item.size}</span>
                            </a>`;
                        }).join('');
                        suggestionsBox.style.display = 'block';
                    } else {
                        suggestionsBox.style.display = 'none';
                    }
                })
                .catch(function() {
                    suggestionsBox.style.display = 'none';
                });
        }, 300);
    });

    // Hide suggestions on blur
    document.addEventListener('click', function(e) {
        if (!suggestionsBox.contains(e.target) && e.target !== searchInput) {
            suggestionsBox.style.display = 'none';
        }
    });
}

// ===== Confirm Helper =====
function confirmAction(message) {
    return confirm(message || '确定要执行此操作吗？');
}

// ===== Toggle Bookmark (AJAX) =====
function toggleBookmark(torrentId, element) {
    ajaxPost('/torrent/' + torrentId + '/bookmark', {},
        function(data) {
            if (data.bookmarked) {
                element.innerHTML = '<i class="bi bi-bookmark-fill text-warning"></i> 已收藏';
                element.classList.add('text-warning');
            } else {
                element.innerHTML = '<i class="bi bi-bookmark"></i> 收藏';
                element.classList.remove('text-warning');
            }
            if (data.count !== undefined) {
                const countEl = document.getElementById('bookmark-count');
                if (countEl) countEl.textContent = data.count;
            }
        }
    );
}

// ===== Thank Uploader (AJAX) =====
function thankUploader(torrentId, element) {
    ajaxPost('/torrent/' + torrentId + '/thank', {},
        function(data) {
            if (data.success) {
                element.disabled = true;
                element.innerHTML = '<i class="bi bi-hand-thumbs-up-fill"></i> 已感谢';
                const countEl = document.getElementById('thank-count');
                if (countEl) countEl.textContent = data.count;
            } else if (data.error) {
                alert(data.error);
            }
        }
    );
}

// ===== Format Bytes =====
function formatBytes(bytes, decimals) {
    if (decimals === undefined) decimals = 2;
    if (bytes === 0) return '0 B';
    var k = 1024;
    var sizes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];
    var i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(decimals)) + ' ' + sizes[i];
}
