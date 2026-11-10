export default function Logo({ size = 34 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" fill="none" aria-hidden="true">
      <rect width="40" height="40" rx="11" fill="#0f766e" />
      <rect x="15.5" y="7" width="9" height="16" rx="4.5" fill="#fff" />
      <path
        d="M11 19v2.5a9 9 0 0 0 18 0V19"
        stroke="#fff"
        strokeWidth="2.6"
        strokeLinecap="round"
      />
      <line x1="20" y1="30.5" x2="20" y2="34.5" stroke="#fbbf24" strokeWidth="2.6" strokeLinecap="round" />
      <path d="M25.5 27.5l2.4 2.4 4.6-4.9" stroke="#fbbf24" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
