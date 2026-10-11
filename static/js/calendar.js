/**
 * Interactive Calendar & Timeline
 * AgriPlan Farm Activity Scheduler
 */

let currentCalendarDate = new Date();
let currentView = 'month'; // 'month' | 'week' | 'day'
let cachedEvents = [];

document.addEventListener('DOMContentLoaded', () => {
  if (document.getElementById('calendarContainer')) {
    loadCalendarEvents();
    
    // Field filter change listener
    const fieldFilter = document.getElementById('calendarFieldFilter');
    if (fieldFilter) {
      fieldFilter.addEventListener('change', () => loadCalendarEvents());
    }
  }
});

async function loadCalendarEvents() {
  const fieldFilter = document.getElementById('calendarFieldFilter');
  const fieldId = fieldFilter ? fieldFilter.value : '';
  const url = fieldId ? `/api/calendar-events?field_id=${fieldId}` : '/api/calendar-events';
  
  try {
    const res = await fetch(url);
    cachedEvents = await res.json();
    renderCalendar();
  } catch (err) {
    console.error('Failed to load events:', err);
  }
}

function switchCalendarView(view) {
  currentView = view;
  document.querySelectorAll('.toggle-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.view === view);
  });
  renderCalendar();
}

function prevPeriod() {
  if (currentView === 'month') {
    currentCalendarDate.setMonth(currentCalendarDate.getMonth() - 1);
  } else if (currentView === 'week') {
    currentCalendarDate.setDate(currentCalendarDate.getDate() - 7);
  } else {
    currentCalendarDate.setDate(currentCalendarDate.getDate() - 1);
  }
  renderCalendar();
}

function nextPeriod() {
  if (currentView === 'month') {
    currentCalendarDate.setMonth(currentCalendarDate.getMonth() + 1);
  } else if (currentView === 'week') {
    currentCalendarDate.setDate(currentCalendarDate.getDate() + 7);
  } else {
    currentCalendarDate.setDate(currentCalendarDate.getDate() + 1);
  }
  renderCalendar();
}

function goToToday() {
  currentCalendarDate = new Date();
  renderCalendar();
}

function renderCalendar() {
  const titleElem = document.getElementById('calendarPeriodTitle');
  const container = document.getElementById('calendarContainer');
  if (!container) return;

  if (currentView === 'month') {
    renderMonthView(container, titleElem);
  } else if (currentView === 'week') {
    renderWeekView(container, titleElem);
  } else {
    renderDayView(container, titleElem);
  }
}

function renderMonthView(container, titleElem) {
  const year = currentCalendarDate.getFullYear();
  const month = currentCalendarDate.getMonth();
  
  const monthNames = ["January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
  ];
  if (titleElem) {
    titleElem.innerText = `${monthNames[month]} ${year}`;
  }

  const firstDay = new Date(year, month, 1).getDay(); // 0 is Sunday
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const daysInPrevMonth = new Date(year, month, 0).getDate();

  let html = `
    <div class="calendar-grid">
      <div class="calendar-day-header">Sun</div>
      <div class="calendar-day-header">Mon</div>
      <div class="calendar-day-header">Tue</div>
      <div class="calendar-day-header">Wed</div>
      <div class="calendar-day-header">Thu</div>
      <div class="calendar-day-header">Fri</div>
      <div class="calendar-day-header">Sat</div>
  `;

  const todayStr = new Date().toISOString().split('T')[0];

  // Previous month trailing days
  for (let i = firstDay - 1; i >= 0; i--) {
    const dayNum = daysInPrevMonth - i;
    html += `<div class="calendar-day-cell other-month"><span class="day-number">${dayNum}</span></div>`;
  }

  // Current month days
  for (let d = 1; d <= daysInMonth; d++) {
    const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
    const isToday = dateStr === todayStr;

    // Filter events starting or spanning this date
    const dayEvents = cachedEvents.filter(ev => {
      return ev.start && ev.start.startsWith(dateStr);
    });

    let eventsHtml = dayEvents.map(ev => {
      const statusClass = ev.status.toLowerCase().replace(' ', '-');
      const conflictBadge = ev.is_conflicted ? '<span style="color:red;" title="Conflict Detected">&#x26A0;</span>' : '';
      return `
        <div class="cal-event-pill ${statusClass} ${ev.is_conflicted ? 'conflict' : ''}" 
             onclick="viewTaskDetails(${ev.id})" title="${ev.title} (${ev.start.substring(11, 16)})">
          ${conflictBadge} ${ev.start.substring(11, 16)} ${ev.title}
        </div>
      `;
    }).join('');

    html += `
      <div class="calendar-day-cell ${isToday ? 'today' : ''}">
        <span class="day-number">${d}</span>
        ${eventsHtml}
      </div>
    `;
  }

  // Fill remaining cells for grid balance
  const totalCells = firstDay + daysInMonth;
  const remainingCells = (7 - (totalCells % 7)) % 7;
  for (let j = 1; j <= remainingCells; j++) {
    html += `<div class="calendar-day-cell other-month"><span class="day-number">${j}</span></div>`;
  }

  html += '</div>';
  container.innerHTML = html;
}

function renderWeekView(container, titleElem) {
  const curr = new Date(currentCalendarDate);
  const first = curr.getDate() - curr.getDay(); // Sunday
  const sunday = new Date(curr.setDate(first));
  const saturday = new Date(curr.setDate(first + 6));

  if (titleElem) {
    titleElem.innerText = `Week of ${sunday.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} - ${saturday.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}`;
  }

  let html = `
    <div style="display: grid; grid-template-columns: repeat(7, 1fr); gap: 12px;">
  `;

  for (let i = 0; i < 7; i++) {
    const day = new Date(sunday);
    day.setDate(sunday.getDate() + i);
    const dateStr = day.toISOString().split('T')[0];
    const isToday = dateStr === new Date().toISOString().split('T')[0];

    const dayEvents = cachedEvents.filter(ev => ev.start && ev.start.startsWith(dateStr));

    html += `
      <div class="card" style="${isToday ? 'border: 2px solid var(--primary-green);' : ''} min-height: 250px;">
        <div class="card-header" style="padding: 10px 14px; background: ${isToday ? 'var(--light-green)' : '#F8FAFC'};">
          <div style="font-weight: 700; font-size: 13px;">${day.toLocaleDateString('en-US', { weekday: 'short' })}</div>
          <div style="font-size: 13px; color: var(--text-muted);">${day.getDate()}</div>
        </div>
        <div class="card-body" style="padding: 12px; display: flex; flex-direction: column; gap: 6px;">
          ${dayEvents.length === 0 ? '<p style="font-size: 12px; color: var(--text-light);">No tasks</p>' : ''}
          ${dayEvents.map(ev => `
            <div class="cal-event-pill ${ev.status.toLowerCase().replace(' ', '-')} ${ev.is_conflicted ? 'conflict' : ''}"
                 onclick="viewTaskDetails(${ev.id})" style="padding: 6px 8px; font-size: 12px;">
              ${ev.is_conflicted ? '<span style="color:red;">&#x26A0;</span> ' : ''}
              <strong>${ev.start.substring(11, 16)}</strong> ${ev.title}
            </div>
          `).join('')}
        </div>
      </div>
    `;
  }

  html += '</div>';
  container.innerHTML = html;
}

function renderDayView(container, titleElem) {
  const dateStr = currentCalendarDate.toISOString().split('T')[0];
  if (titleElem) {
    titleElem.innerText = currentCalendarDate.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' });
  }

  const dayEvents = cachedEvents.filter(ev => ev.start && ev.start.startsWith(dateStr));

  let html = `
    <div class="card">
      <div class="card-header">
        <h3 class="card-title">Tasks Scheduled for ${titleElem ? titleElem.innerText : 'Day'}</h3>
        <span class="badge badge-completed">${dayEvents.length} Tasks</span>
      </div>
      <div class="card-body">
  `;

  if (dayEvents.length === 0) {
    html += '<p style="color: var(--text-muted); text-align: center; padding: 30px;">No farming tasks scheduled for this day.</p>';
  } else {
    html += `
      <div style="display: flex; flex-direction: column; gap: 12px;">
        ${dayEvents.map(ev => `
          <div style="border: 1px solid var(--border-color); border-left: 5px solid ${ev.is_conflicted ? 'var(--error-red)' : 'var(--primary-green)'}; padding: 14px 18px; border-radius: var(--radius-sm); display: flex; justify-content: space-between; align-items: center; cursor: pointer;"
               onclick="viewTaskDetails(${ev.id})">
            <div>
              <div style="font-weight: 700; font-size: 15px; color: var(--dark-text);">
                ${ev.is_conflicted ? '<span style="color:red;">&#x26A0; CONFLICT: </span>' : ''} ${ev.title}
              </div>
              <div style="font-size: 13px; color: var(--text-muted); margin-top: 4px;">
                Field: <strong>${ev.field_name}</strong> &bull; Worker: <strong>${ev.worker_name}</strong> &bull; Equip: <strong>${ev.equipment_name}</strong>
              </div>
            </div>
            <div style="text-align: right;">
              <div style="font-weight: 600; font-size: 14px; color: var(--forest-green);">${ev.start.substring(11, 16)} - ${ev.end.substring(11, 16)}</div>
              <span class="badge badge-${ev.status.toLowerCase().replace(' ', '-')}" style="margin-top: 4px;">${ev.status}</span>
            </div>
          </div>
        `).join('')}
      </div>
    `;
  }

  html += '</div></div>';
  container.innerHTML = html;
}
