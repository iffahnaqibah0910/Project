"use client";

import { Line } from "react-chartjs-2";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  TimeScale,
} from "chart.js";
import "chartjs-adapter-date-fns";

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, TimeScale);

const AMBER = "#e0a640";
const GREEN = "#5fae7d";
const DIM = "#8ba39b";

function timeUnitForSpan(timestamps) {
  const times = timestamps
    .map((t) => new Date(t).getTime())
    .filter((n) => Number.isFinite(n));
  if (times.length < 2) return "day";

  const spanMs = Math.max(...times) - Math.min(...times);
  const day = 24 * 60 * 60 * 1000;
  if (spanMs > 180 * day) return "month";
  if (spanMs > 14 * day) return "day";
  if (spanMs > day) return "hour";
  return "minute";
}

export default function RollingChart({ eda, sensor = "RUNTIME_SEC" }) {
  if (!eda) return <div className="chart-empty">Loading EDA…</div>;
  if (eda.length === 0) return <div className="chart-empty">No chart data for this factory.</div>;

  const labels = eda.map((d) => d.timestamp);
  const mean = eda.map((d) => d[`${sensor}_roll_mean`]);
  const std = eda.map((d) => d[`${sensor}_roll_std`]);
  const upper = mean.map((m, i) => (m != null && std[i] != null ? m + 2 * std[i] : null));
  const lower = mean.map((m, i) => (m != null && std[i] != null ? m - 2 * std[i] : null));
  const xUnit = timeUnitForSpan(labels);

  const data = {
    labels,
    datasets: [
      {
        label: `${sensor} mean`,
        data: mean,
        borderColor: AMBER,
        backgroundColor: "transparent",
        pointRadius: 0,
        borderWidth: 2,
        tension: 0.25,
        pointStyle: "line",
      },
      {
        label: "+2σ",
        data: upper,
        borderColor: "rgba(224,166,64,0.45)",
        backgroundColor: "transparent",
        pointRadius: 0,
        borderWidth: 1.5,
        borderDash: [3, 3],
        pointStyle: "line",
      },
      {
        label: "-2σ",
        data: lower,
        borderColor: "rgba(224,166,64,0.45)",
        backgroundColor: "transparent",
        pointRadius: 0,
        borderWidth: 1.5,
        borderDash: [3, 3],
        pointStyle: "line",
      },
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    plugins: {
      legend: {
        labels: {
          color: DIM,
          font: { family: "Inter", size: 11 },
          usePointStyle: true,
          pointStyleWidth: 22,
          generateLabels(chart) {
            const items = ChartJS.defaults.plugins.legend.labels.generateLabels(chart);
            return items.map((item) => {
              const isSigma = item.text === "+2σ" || item.text === "-2σ";
              return {
                ...item,
                pointStyle: "line",
                lineWidth: isSigma ? 1.5 : 2,
                lineDash: isSigma ? [3, 3] : [],
              };
            });
          },
        },
      },
      tooltip: { mode: "index", intersect: false },
    },
    scales: {
      x: {
        type: "time",
        time: { unit: xUnit },
        ticks: { color: DIM, maxTicksLimit: 8 },
        grid: { color: "rgba(34,51,48,0.6)" },
      },
      y: {
        ticks: { color: DIM },
        grid: { color: "rgba(34,51,48,0.6)" },
      },
    },
  };

  return (
    <div style={{ height: 280 }}>
      <Line data={data} options={options} />
    </div>
  );
}