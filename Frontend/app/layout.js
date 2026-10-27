import "./globals.css";

export const metadata = {
  title: "Automated Missing Value Error Detection Dashboard",
  description: "Real-time monitoring for missingness, EDA, and anomaly detection",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
