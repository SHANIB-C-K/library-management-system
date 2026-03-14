/**
 * main.js — Global JavaScript for the Library Management System
 * Initializes AOS animations, Lucide icons, SweetAlert2 helpers, and page loading bar.
 */

document.addEventListener('DOMContentLoaded', () => {

    // ── AOS Animations ────────────────────────────────────────────────────
    AOS.init({ duration: 700, once: true, offset: 40 });

    // ── Lucide Icons ──────────────────────────────────────────────────────
    lucide.createIcons();

    // ── Top Loading Bar ───────────────────────────────────────────────────
    const bar = document.createElement('div');
    bar.id = 'topLoadingBar';
    bar.style.cssText = `
        position: fixed; top: 0; left: 0; height: 3px; width: 0%;
        background: linear-gradient(90deg, #3b82f6, #8b5cf6, #06b6d4);
        z-index: 9999; transition: width 0.4s ease, opacity 0.3s ease;
        box-shadow: 0 0 10px rgba(59,130,246,0.6);
        border-radius: 0 2px 2px 0;
    `;
    document.body.appendChild(bar);

    function startLoadingBar() {
        bar.style.width = '70%';
        bar.style.opacity = '1';
    }
    function finishLoadingBar() {
        bar.style.width = '100%';
        setTimeout(() => { bar.style.opacity = '0'; bar.style.width = '0%'; }, 300);
    }

    // Trigger on page show (including back/forward cache)
    window.addEventListener('pageshow', finishLoadingBar);
    finishLoadingBar(); // Also run on initial load

    // Intercept all link clicks to show loading bar
    document.body.addEventListener('click', (e) => {
        const link = e.target.closest('a');
        if (link && link.href && !link.href.startsWith('#') &&
            !link.target && link.origin === window.location.origin) {
            startLoadingBar();
        }
    });

    // Show bar on form submissions
    document.body.addEventListener('submit', () => startLoadingBar());

    // ── Dialog: click outside to close ────────────────────────────────────
    document.querySelectorAll('dialog').forEach(dialog => {
        dialog.addEventListener('click', (e) => {
            const rect = dialog.getBoundingClientRect();
            if (e.clientX < rect.left || e.clientX > rect.right ||
                e.clientY < rect.top  || e.clientY > rect.bottom) {
                dialog.close();
            }
        });
    });
});

// ── Deletion Confirmation (SweetAlert2) ───────────────────────────────────
function confirmDeletion(url, title = 'Confirm Deletion', text = "This action cannot be undone.") {
    Swal.fire({
        title:              title,
        text:               text,
        icon:               'warning',
        showCancelButton:   true,
        confirmButtonColor: '#ef4444',
        cancelButtonColor:  '#475569',
        confirmButtonText:  '<i class="swal2-icon-error"></i> Yes, delete',
        cancelButtonText:   'Cancel',
        background:         '#0f172a',
        color:              '#f1f5f9',
        customClass: {
            popup:         'rounded-2xl border border-slate-700 shadow-2xl',
            confirmButton: 'rounded-xl px-5 font-semibold',
            cancelButton:  'rounded-xl px-5 font-semibold',
        }
    }).then((result) => {
        if (result.isConfirmed) {
            // Show loading bar before navigating
            document.getElementById('topLoadingBar').style.width   = '70%';
            document.getElementById('topLoadingBar').style.opacity = '1';

            fetch(url, { method: 'POST' })
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        Swal.fire({
                            title:              'Deleted!',
                            text:               'The record has been removed.',
                            icon:               'success',
                            background:         '#0f172a',
                            color:              '#f1f5f9',
                            confirmButtonColor: '#22c55e',
                            customClass: {
                                popup:         'rounded-2xl border border-slate-700',
                                confirmButton: 'rounded-xl px-5 font-semibold',
                            }
                        }).then(() => window.location.reload());
                    } else {
                        Swal.fire({
                            title:  'Error',
                            text:   data.message || 'Could not delete the record.',
                            icon:   'error',
                            background: '#0f172a',
                            color:  '#f1f5f9',
                            confirmButtonColor: '#ef4444',
                            customClass: {
                                popup:         'rounded-2xl border border-slate-700',
                                confirmButton: 'rounded-xl px-5 font-semibold',
                            }
                        });
                    }
                })
                .catch(() => Swal.fire('Error', 'Network error occurred.', 'error'));
        }
    });
}
