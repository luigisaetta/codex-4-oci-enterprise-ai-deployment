import "./globals.css";
import { demo } from "./demo-config";

export const metadata = {
  title: demo.title,
  description: demo.story,
};

export default function RootLayout({ children }) {
  return (
    <html lang={demo.language}>
      <body>{children}</body>
    </html>
  );
}
