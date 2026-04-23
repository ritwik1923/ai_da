// Professional chart theme utilities
export const PROFESSIONAL_COLORS = [
  '#0F766E', // teal-800
  '#0369A1', // sky-700
  '#7C3AED', // violet-600
  '#DC2626', // red-600
  '#EA580C', // orange-600
  '#EAB308', // yellow-400
  '#10B981', // emerald-600
  '#F97316', // orange-500
];

export const ACCENT_COLORS = {
  primary: '#0F766E',
  secondary: '#0369A1',
  accent: '#7C3AED',
  success: '#10B981',
  warning: '#F97316',
  danger: '#DC2626',
};

/**
 * Enhance Plotly chart layout with professional styling
 */
export function enhanceChartLayout(layout: any, isDarkMode = false) {
  const bgColor = isDarkMode ? '#1F2937' : '#FFFFFF';
  const textColor = isDarkMode ? '#F3F4F6' : '#1F2937';
  const gridColor = isDarkMode ? '#374151' : '#E5E7EB';

  return {
    ...layout,
    font: {
      family: 'Inter, system-ui, -apple-system, sans-serif',
      size: 12,
      color: textColor,
      ...layout.font,
    },
    plot_bgcolor: bgColor,
    paper_bgcolor: bgColor,
    showlegend: true,
    hovermode: 'closest',
    margin: {
      l: 70,
      r: 50,
      t: 60,
      b: 70,
      ...layout.margin,
    },
    xaxis: {
      ...layout.xaxis,
      showgrid: true,
      gridwidth: 1,
      gridcolor: gridColor,
      showline: true,
      linewidth: 2,
      linecolor: gridColor,
      mirror: false,
      zeroline: false,
      font: {
        size: 12,
        color: textColor,
      },
    },
    yaxis: {
      ...layout.yaxis,
      showgrid: true,
      gridwidth: 1,
      gridcolor: gridColor,
      showline: true,
      linewidth: 2,
      linecolor: gridColor,
      mirror: false,
      zeroline: false,
      font: {
        size: 12,
        color: textColor,
      },
    },
    title: {
      ...layout.title,
      font: {
        size: 18,
        color: textColor,
        family: 'Inter, system-ui, -apple-system, sans-serif',
      },
      x: 0.5,
      xanchor: 'center',
    },
    legend: {
      ...layout.legend,
      bgcolor: `rgba(255, 255, 255, 0.8)`,
      bordercolor: gridColor,
      borderwidth: 1,
      font: {
        size: 12,
        color: textColor,
      },
    },
  };
}

/**
 * Enhance chart data series with professional colors and styling
 */
export function enhanceChartData(data: any[], _isDarkMode = false) {
  return data.map((trace: any, index: number) => {
    const color = PROFESSIONAL_COLORS[index % PROFESSIONAL_COLORS.length];

    // Handle different trace types
    if (trace.type === 'bar') {
      return {
        ...trace,
        marker: {
          ...trace.marker,
          color: trace.marker?.color || color,
          line: {
            color: 'rgba(0, 0, 0, 0.1)',
            width: 0.5,
          },
          opacity: 0.85,
        },
        hovertemplate:
          trace.hovertemplate ||
          '<b>%{x}</b><br>Value: %{y:,.2f}<extra></extra>',
      };
    }

    if (trace.type === 'scatter' || !trace.type) {
      return {
        ...trace,
        line: {
          ...trace.line,
          color: trace.line?.color || color,
          width: 3,
        },
        marker: {
          ...trace.marker,
          size: 8,
          color: trace.marker?.color || color,
          line: {
            color: '#FFFFFF',
            width: 2,
          },
          opacity: 0.9,
        },
        fill: trace.fill || 'tozeroy',
        fillcolor: `rgba(${hexToRgb(color)}, 0.1)`,
        hovertemplate:
          trace.hovertemplate ||
          '<b>%{x}</b><br>Value: %{y:,.2f}<extra></extra>',
      };
    }

    if (trace.type === 'box' || trace.type === 'violin') {
      return {
        ...trace,
        marker: {
          ...trace.marker,
          color: color,
          opacity: 0.7,
        },
        line: {
          color: color,
          width: 2,
        },
      };
    }

    if (trace.type === 'pie') {
      return {
        ...trace,
        marker: {
          ...trace.marker,
          colors: PROFESSIONAL_COLORS,
          line: {
            color: '#FFFFFF',
            width: 2,
          },
        },
        hovertemplate:
          trace.hovertemplate ||
          '<b>%{label}</b><br>Value: %{value}<br>Percentage: %{percent}<extra></extra>',
      };
    }

    return trace;
  });
}

/**
 * Convert hex color to RGB
 */
function hexToRgb(hex: string): string {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  if (result) {
    const r = parseInt(result[1], 16);
    const g = parseInt(result[2], 16);
    const b = parseInt(result[3], 16);
    return `${r}, ${g}, ${b}`;
  }
  return '0, 0, 0';
}

export function getProfessionalChartConfig() {
  return {
    responsive: true,
    displayModeBar: true,
    displaylogo: false,
    modeBarButtonsToRemove: ['lasso2d', 'select2d'],
    toImageButtonOptions: {
      format: 'png',
      filename: 'chart.png',
      height: 800,
      width: 1200,
      scale: 2,
    },
  };
}
