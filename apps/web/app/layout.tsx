import "./globals.css";

export const metadata = {
  title: "SpeakFill",
  description: "Speak. Confirm. Done.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
