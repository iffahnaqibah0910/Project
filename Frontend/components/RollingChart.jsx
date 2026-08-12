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

export default function RollingChart({ eda, sensor = "MACHCODE" }) {
  if (!eda || eda.length === 0) return <div className="chart-empty">Loading EDA…</div>;

  const labels = eda.map((d) => d.timestamp);
  const mean = eda.map((d) => d[`${sensor}_roll_mean`]);
  const std = eda.map((d) => d[`${sensor}_roll_std`]);
  const upper = mean.map((m, i) => (m != null && std[i] != null ? m + 2 * std[i] : null));
  const lower = mean.map((m, i) => (m != null && std[i] != null ? m - 2 * std[i] : null));

  const data = {
    labels,
    datasets: [
      {
        label: `${sensor} rolling mean`,
        data: mean,
        borderColor: AMBER,
        backgroundColor: "transparent",
        pointRadius: 0,
        borderWidth: 2,
        tension: 0.25,
      },
      {
        label: "+2σ",
        data: upper,
        borderColor: "rgba(224,166,64,0.25)",
        backgroundColor: "transparent",
        pointRadius: 0,
        borderWidth: 1,
        borderDash: [4, 4],
      },
      {
        label: "-2σ",
        data: lower,
        borderColor: "rgba(224,166,64,0.25)",
        backgroundColor: "transparent",
        pointRadius: 0,
        borderWidth: 1,
        borderDash: [4, 4],
      },
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    plugins: {
      legend: { labels: { color: DIM, font: { family: "Inter", size: 11 } } },
      tooltip: { mode: "index", intersect: false },
    },
    scales: {
      x: {
        type: "time",
        time: { unit: "minute" },
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