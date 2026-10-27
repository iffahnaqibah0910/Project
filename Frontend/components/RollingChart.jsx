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

const AMBER = "#9a6410";
const DIM = "#5d726a";
const GRID = "rgba(28, 40, 36, 0.1)";

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

export default function RollingChart({ eda, sensor = "DAILY_MC_RATIO" }) {
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
        label: `${sensor} Mean`,
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
        borderColor: "rgba(154,100,16,0.45)",
        backgroundColor: "transparent",
        pointRadius: 0,
        borderWidth: 1.5,
        borderDash: [3, 3],
        pointStyle: "line",
      },
      {
        label: "-2σ",
        data: lower,
        borderColor: "rgba(154,100,16,0.45)",
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
      legend: { display: false },
      tooltip: {
        mode: "index",
        intersect: false,
        backgroundColor: "#ffffff",
        titleColor: "#1c2824",
        bodyColor: "#5d726a",
        borderColor: "#d3dcd8",
        borderWidth: 1,
      },
    },
    scales: {
      x: {
        type: "time",
        time: { unit: xUnit, tooltipFormat: "MMM d, yyyy" },
        ticks: { color: DIM, maxTicksLimit: 8 },
        grid: { color: GRID },
        border: { color: GRID },
      },
      y: {
        max: 85,
        ticks: { color: DIM, stepSize: 5 },
        grid: { color: GRID },
        border: { color: GRID },
      },
    },
  };

  return (
    <div style={{ height: 312 }}>
      <Line data={data} options={options} />
    </div>
  );
}