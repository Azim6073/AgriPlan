/**
 * Dashboard Charts Renderer using Chart.js
 */

function initDashboardCharts(cropData, statusData) {
  // 1. Crop Distribution Chart (Doughnut)
  const cropCtx = document.getElementById('cropDistributionChart');
  if (cropCtx && cropData) {
    new Chart(cropCtx, {
      type: 'doughnut',
      data: {
        labels: cropData.labels,
        datasets: [{
          data: cropData.data,
          backgroundColor: [
            '#2E8B57', // Forest green
            '#F59E0B', // Amber
            '#3B82F6', // Blue
            '#10B981', // Emerald
            '#8B5CF6', // Purple
            '#EC4899'  // Pink
          ],
          borderWidth: 2,
          borderColor: '#FFFFFF'
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: 'bottom',
            labels: {
              boxWidth: 12,
              font: { family: 'Inter', size: 12 }
            }
          }
        },
        cutout: '65%'
      }
    });
  }

  // 2. Task Status Breakdown Chart (Bar)
  const statusCtx = document.getElementById('taskStatusChart');
  if (statusCtx && statusData) {
    new Chart(statusCtx, {
      type: 'bar',
      data: {
        labels: statusData.labels,
        datasets: [{
          label: 'Count',
          data: statusData.data,
          backgroundColor: [
            '#10B981', // Completed (green)
            '#3B82F6', // In Progress / Pending (blue)
            '#EF4444', // Overdue (red)
            '#F59E0B'  // Conflicts (orange)
          ],
          borderRadius: 6
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false }
        },
        scales: {
          y: {
            beginAtZero: true,
            ticks: { stepSize: 1, precision: 0 },
            grid: { color: '#F1F5F9' }
          },
          x: {
            grid: { display: false }
          }
        }
      }
    });
  }
}
