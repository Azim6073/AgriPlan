/**
 * AgriPlan - Global Application JavaScript
 * Handles Modals, Flash dismissal, Quick Actions, and Reschedule AJAX
 */

document.addEventListener('DOMContentLoaded', () => {
  // 1. Auto-dismiss flash alerts after 5 seconds
  setTimeout(() => {
    document.querySelectorAll('.alert').forEach(alert => {
      alert.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
      alert.style.opacity = '0';
      alert.style.transform = 'translateY(-10px)';
      setTimeout(() => alert.remove(), 400);
    });
  }, 6000);

  // 2. Close modal on backdrop click
  document.querySelectorAll('.modal-overlay').forEach(modal => {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) {
        closeModal(modal.id);
      }
    });
  });

  // 3. Escape key closes open modal
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      document.querySelectorAll('.modal-overlay.active').forEach(modal => {
        closeModal(modal.id);
      });
    }
  });
});

// Modal helpers
function openModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) {
    modal.classList.add('active');
    document.body.style.overflow = 'hidden';
  }
}

function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) {
    modal.classList.remove('active');
    document.body.style.overflow = '';
  }
}

// Quick View Task Modal via AJAX
async function viewTaskDetails(taskId) {
  try {
    const res = await fetch(`/tasks/${taskId}`);
    if (!res.ok) throw new Error('Task details not found');
    const data = await res.json();
    const t = data.task;

    const modalBody = document.getElementById('taskDetailModalBody');
    if (!modalBody) return;

    let prereqHtml = '<p class="text-muted" style="font-size: 13px;">None</p>';
    if (data.prerequisites && data.prerequisites.length > 0) {
      prereqHtml = '<ul style="padding-left: 20px; font-size: 13px;">' + 
        data.prerequisites.map(p => `<li><strong>${p.title}</strong> — <span class="badge badge-${p.status.toLowerCase().replace(' ', '-')}">${p.status}</span></li>`).join('') +
        '</ul>';
    }

    let startWarningHtml = '';
    if (!data.can_start) {
      startWarningHtml = `
        <div class="alert alert-warning" style="margin-top: 12px; font-size: 13px;">
          <strong>Cannot Start:</strong> ${data.start_reason}
        </div>
      `;
    }

    modalBody.innerHTML = `
      <div style="margin-bottom: 16px;">
        <h3 style="font-size: 18px; font-weight: 700; color: var(--dark-text);">${t.title}</h3>
        <p style="color: var(--text-muted); font-size: 13px;">${t.field_name} &bull; ${t.crop_name || 'No crop specified'}</p>
      </div>

      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; font-size: 13px; margin-bottom: 16px;">
        <div><strong>Type:</strong> ${t.task_type}</div>
        <div><strong>Priority:</strong> <span class="badge badge-priority-${t.priority.toLowerCase()}">${t.priority}</span></div>
        <div><strong>Status:</strong> <span class="badge badge-${t.status.toLowerCase().replace(' ', '-')}">${t.status}</span></div>
        <div><strong>Assigned Worker:</strong> ${t.worker_name || 'None'}</div>
        <div><strong>Equipment:</strong> ${t.equipment_name || 'None'}</div>
        <div><strong>Start:</strong> ${t.start_datetime.replace('T', ' ')}</div>
        <div><strong>End:</strong> ${t.end_datetime.replace('T', ' ')}</div>
        <div><strong>Deadline:</strong> ${t.deadline ? t.deadline.replace('T', ' ') : 'None'}</div>
      </div>

      <div style="margin-bottom: 16px;">
        <strong style="font-size: 13px;">Prerequisite Tasks:</strong>
        ${prereqHtml}
      </div>

      ${startWarningHtml}

      ${t.description ? `<div style="background: #f8fafc; padding: 12px; border-radius: 6px; font-size: 13px;"><strong>Notes:</strong> ${t.description}</div>` : ''}
    `;

    openModal('taskDetailModal');
  } catch (err) {
    alert('Error fetching task details: ' + err.message);
  }
}

// Smart Reschedule Suggestion Loader
async function loadRescheduleSuggestions(taskId, containerId) {
  const container = document.getElementById(containerId);
  if (!container) return;

  container.innerHTML = `
    <div style="text-align: center; padding: 20px; color: var(--text-muted);">
      <span style="display: inline-block; animation: spin 1s infinite linear;">&#x21bb;</span> Calculating non-overlapping alternatives with rule engine...
    </div>
  `;

  try {
    const res = await fetch(`/api/tasks/${taskId}/reschedule-suggestions`);
    const data = await res.json();

    if (!data.success || !data.suggestions || data.suggestions.length === 0) {
      container.innerHTML = `
        <div style="padding: 12px; background: #fff3cd; color: #856404; border-radius: 6px; font-size: 13px;">
          No free daytime slots found in the upcoming 7 days without creating conflicts. Try unassigning or reallocating resources.
        </div>
      `;
      return;
    }

    let itemsHtml = data.suggestions.map(s => `
      <div class="suggestion-item">
        <div>
          <div class="suggestion-time">${s.display_start} &rarr; ${s.display_end}</div>
          <div class="suggestion-reason">${s.rationale}</div>
        </div>
        <button type="button" class="btn btn-sm btn-primary" onclick="confirmReschedule(${taskId}, '${s.start_datetime}', '${s.end_datetime}')">
          Accept Slot
        </button>
      </div>
    `).join('');

    container.innerHTML = `
      <div class="suggestion-box">
        <div class="suggestion-title">&#x26A1; Available Non-Conflicting Time Slots (Duration: ${data.duration_str})</div>
        <div class="suggestion-list">${itemsHtml}</div>
      </div>
    `;
  } catch (err) {
    container.innerHTML = `<div style="color: var(--error-red); font-size: 13px;">Failed to load suggestions: ${err.message}</div>`;
  }
}

// Apply selected reschedule slot
async function confirmReschedule(taskId, startDt, endDt) {
  if (!confirm(`Confirm reschedule to: ${startDt.replace('T', ' ')}? This will atomically update the database.`)) {
    return;
  }

  try {
    const res = await fetch(`/api/tasks/${taskId}/reschedule`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ start_datetime: startDt, end_datetime: endDt })
    });
    const result = await res.json();
    if (result.success) {
      alert(result.message);
      window.location.reload();
    } else {
      alert('Reschedule error: ' + result.message);
    }
  } catch (err) {
    alert('Failed to apply reschedule: ' + err.message);
  }
}

// Notification mark read helper
async function markNotifRead(notifId, element) {
  try {
    const res = await fetch(`/api/notifications/mark-read/${notifId}`, { method: 'POST' });
    const data = await res.json();
    if (data.success) {
      element.closest('.notif-card').classList.add('read');
      element.remove();
    }
  } catch (err) {
    console.error(err);
  }
}
