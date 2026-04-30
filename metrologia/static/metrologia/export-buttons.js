/**
 * Export Buttons Enhancement - Fase 5
 * Funcionalidades de feedback visual e interatividade
 */

(function() {
    'use strict';

    /**
     * Initialize export button enhancements
     */
    function initExportButtons() {
        const exportButtons = document.querySelectorAll('[data-export-format]');
        
        exportButtons.forEach(button => {
            addLoadingState(button);
            addTooltips(button);
            addAnalytics(button);
        });
    }

    /**
     * Add loading state to export buttons
     */
    function addLoadingState(button) {
        button.addEventListener('click', function(e) {
            // Store original content
            const originalHTML = button.innerHTML;
            const format = button.getAttribute('data-export-format');
            
            // Add loading spinner
            const spinner = document.createElement('span');
            spinner.className = 'export-loading';
            spinner.innerHTML = '<i class="bi bi-hourglass-split"></i>';
            
            // Update button text
            button.innerHTML = '';
            button.appendChild(spinner);
            button.innerHTML += ` Gerando ${format.toUpperCase()}...`;
            button.disabled = true;
            
            // Restore after delay (file download is instant)
            setTimeout(() => {
                button.innerHTML = originalHTML;
                button.disabled = false;
            }, 1500);
        });
    }

    /**
     * Add Bootstrap tooltips to export items
     */
    function addTooltips(element) {
        const tooltip = element.getAttribute('title');
        if (tooltip) {
            new bootstrap.Tooltip(element);
        }
    }

    /**
     * Track export analytics
     */
    function addAnalytics(button) {
        button.addEventListener('click', function() {
            const format = button.getAttribute('data-export-format');
            const page = button.getAttribute('data-export-page') || 'unknown';
            
            // Log to console for debugging
            console.log(`[EXPORT] Format: ${format}, Page: ${page}, Time: ${new Date().toISOString()}`);
            
            // Send to analytics if available
            if (typeof gtag !== 'undefined') {
                gtag('event', 'export', {
                    'export_format': format,
                    'export_page': page
                });
            }
        });
    }

    /**
     * Enhanced dropdown menu with keyboard navigation
     */
    function initKeyboardNavigation() {
        const dropdownMenus = document.querySelectorAll('.dropdown-menu');
        
        dropdownMenus.forEach(menu => {
            const items = menu.querySelectorAll('a, button');
            
            items.forEach((item, index) => {
                item.addEventListener('keydown', function(e) {
                    let nextItem;
                    
                    if (e.key === 'ArrowDown') {
                        e.preventDefault();
                        nextItem = items[index + 1];
                        if (nextItem) nextItem.focus();
                    } else if (e.key === 'ArrowUp') {
                        e.preventDefault();
                        nextItem = items[index - 1];
                        if (nextItem) nextItem.focus();
                    } else if (e.key === 'Enter') {
                        item.click();
                    }
                });
            });
        });
    }

    /**
     * Show export stats in UI
     */
    function updateExportStats() {
        const exportStats = document.querySelector('[data-export-total]');
        if (exportStats) {
            const total = exportStats.getAttribute('data-export-total');
            const statsElement = document.createElement('span');
            statsElement.className = 'export-stats';
            statsElement.innerHTML = `
                <i class="bi bi-file-earmark-arrow-down"></i>
                <span>${total} registros prontos para exportar</span>
            `;
            
            const exportBtn = document.querySelector('.export-dropdown-btn');
            if (exportBtn) {
                exportBtn.parentElement.insertBefore(statsElement, exportBtn);
            }
        }
    }

    /**
     * Add format descriptions
     */
    function addFormatDescriptions() {
        const excelItems = document.querySelectorAll('[data-format="excel"]');
        const csvItems = document.querySelectorAll('[data-format="csv"]');
        const pdfItems = document.querySelectorAll('[data-format="pdf"]');
        
        excelItems.forEach(item => {
            addDescription(item, 'Formato Excel (.xlsx) - Melhor para análises em planilhas');
        });
        
        csvItems.forEach(item => {
            addDescription(item, 'Formato CSV - Compatível com todos os sistemas');
        });
        
        pdfItems.forEach(item => {
            addDescription(item, 'Formato PDF - Pronto para impressão e compartilhamento');
        });
    }

    function addDescription(item, description) {
        const desc = document.createElement('p');
        desc.className = 'export-format-desc';
        desc.textContent = description;
        item.appendChild(desc);
    }

    /**
     * Initialize all enhancements
     */
    function init() {
        document.addEventListener('DOMContentLoaded', function() {
            initExportButtons();
            initKeyboardNavigation();
            updateExportStats();
            addFormatDescriptions();
        });
    }

    // Initialize on script load
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
