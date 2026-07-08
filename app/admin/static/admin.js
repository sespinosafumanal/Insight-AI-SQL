/* =========================================================
   Insight AI-SQL — Admin Panel · admin.js
   ========================================================= */

'use strict';

// ─── TOAST NOTIFICATIONS ─────────────────────────────────
/**
 * Show a toast notification.
 * @param {string} message
 * @param {'success'|'error'|'info'} type
 */
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const icons = {
        success: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="#22c55e"><path stroke-linecap="round" stroke-linejoin="round" d="m4.5 12.75 6 6 9-13.5"/></svg>`,
        error: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="#ef4444"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18 18 6M6 6l12 12"/></svg>`,
        info: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="#3b82f6"><path stroke-linecap="round" stroke-linejoin="round" d="m11.25 11.25.041-.02a.75.75 0 0 1 1.063.852l-.708 2.836a.75.75 0 0 0 1.063.853l.041-.021M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9-3.75h.008v.008H12V8.25Z"/></svg>`,
    };

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `${icons[type] || icons.info}<span>${message}</span>`;
    container.appendChild(toast);

    setTimeout(() => toast.remove(), 3200);
}


// ─── COPY SQL TO CLIPBOARD ───────────────────────────────
function copySql() {
    const codeEl = document.querySelector('#sql-display code');
    const btn = document.getElementById('copy-sql-btn');
    if (!codeEl || !btn) return;

    const text = codeEl.textContent;

    navigator.clipboard.writeText(text).then(() => {
        btn.classList.add('copied');
        btn.innerHTML = `
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" d="m4.5 12.75 6 6 9-13.5"/>
            </svg>
            Copiado
        `;
        showToast('SQL copiado al portapapeles', 'success');

        setTimeout(() => {
            btn.classList.remove('copied');
            btn.innerHTML = `
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 17.25v3.375c0 .621-.504 1.125-1.125 1.125h-9.75a1.125 1.125 0 0 1-1.125-1.125V7.875c0-.621.504-1.125 1.125-1.125H6.75a9.06 9.06 0 0 1 1.5.124m7.5 10.376h3.375c.621 0 1.125-.504 1.125-1.125V11.25c0-4.46-3.243-8.161-7.5-8.876a9.06 9.06 0 0 0-1.5-.124H9.375c-.621 0-1.125.504-1.125 1.125v3.5m7.5 10.375H9.375a1.125 1.125 0 0 1-1.125-1.125v-9.25m12 6.625v-1.875a3.375 3.375 0 0 0-3.375-3.375h-1.5a1.125 1.125 0 0 1-1.125-1.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H9.75"/>
                </svg>
                Copiar
            `;
        }, 2200);
    }).catch(() => {
        showToast('No se pudo copiar al portapapeles', 'error');
    });
}


// ─── INLINE CONFIRMATION (REPLACES window.confirm) ─────────
function confirmAction(event, btn) {
    // Si ya estamos en fase de confirmación, dejamos que el formulario se envíe
    if (btn.dataset.confirmPhase === '2') {
        return true;
    }

    // Detenemos el envío en el primer clic
    event.preventDefault();

    // Guardamos estado original
    if (!btn.dataset.originalHtml) {
        btn.dataset.originalHtml = btn.innerHTML;
        btn.dataset.originalClass = btn.className;
    }

    // Pasamos a fase 2
    btn.dataset.confirmPhase = '2';
    btn.classList.add('confirm-phase-2');

    // Cambiar contenido a "¿Seguro?" con un icono de check
    btn.innerHTML = `
        <svg width="15" height="15" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" d="m4.5 12.75 6 6 9-13.5"/>
        </svg>
        <span>¿Seguro?</span>
    `;

    // Cancelar la confirmación si no hacen clic después de 3.5 segundos
    const timeoutId = setTimeout(() => {
        if (btn.dataset.confirmPhase === '2') {
            btn.dataset.confirmPhase = '1';
            btn.classList.remove('confirm-phase-2');
            btn.innerHTML = btn.dataset.originalHtml;
        }
    }, 3500);

    // Guardar timeout para poder limpiarlo si fuera necesario
    btn.dataset.timeoutId = timeoutId;

    return false;
}


// ─── LIVE TABLE SEARCH ───────────────────────────────────
function initTableSearch() {
    const input = document.getElementById('search-input');
    const tbody = document.getElementById('candidates-tbody');
    if (!input || !tbody) return;

    input.addEventListener('input', () => {
        const query = input.value.trim().toLowerCase();
        const rows = tbody.querySelectorAll('tr');
        let visible = 0;

        rows.forEach(row => {
            const haystack = (row.dataset.search || row.textContent).toLowerCase();
            const matches = query === '' || haystack.includes(query);
            row.style.display = matches ? '' : 'none';
            if (matches) visible++;
        });

        // Show no-results message if all rows are hidden
        let noResultsRow = tbody.querySelector('.no-results-row');
        if (visible === 0 && query !== '') {
            if (!noResultsRow) {
                const cols = tbody.closest('table')?.querySelectorAll('thead th').length || 5;
                noResultsRow = document.createElement('tr');
                noResultsRow.className = 'no-results-row';
                noResultsRow.innerHTML = `<td colspan="${cols}" style="text-align:center;padding:32px;color:var(--text-muted);font-size:0.85rem;">No se encontraron resultados para "<strong>${escapeHtml(query)}</strong>"</td>`;
                tbody.appendChild(noResultsRow);
            }
        } else if (noResultsRow) {
            noResultsRow.remove();
        }
    });
}


// ─── UTILS ───────────────────────────────────────────────
function escapeHtml(str) {
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}


// ─── INIT ────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    initTableSearch();

    // Toggle para el menú desplegable de Consultas SQL (movido a layout.html como inline onclick)
    /*
    const sqlToggle = document.getElementById('nav-sql-toggle');
    if (sqlToggle) {
        sqlToggle.addEventListener('click', (e) => {
            e.preventDefault();
            const dropdown = sqlToggle.closest('.nav-item-dropdown');
            if (dropdown) {
                dropdown.classList.toggle('open');
            }
        });
    }
    */
});

