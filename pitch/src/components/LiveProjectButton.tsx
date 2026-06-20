interface LiveProjectButtonProps {
  label?: string;
  href?: string;
  tone?: "light" | "dark";
}

const LIGHT_CLASS =
  "inline-block rounded-full border-2 border-[#D7E2EA] text-[#D7E2EA] font-medium uppercase tracking-widest px-8 py-3 sm:px-10 sm:py-3.5 text-sm sm:text-base hover:bg-[#D7E2EA]/10 transition-colors duration-200";
const DARK_CLASS =
  "inline-block rounded-full border-2 border-[#0C0C0C] text-[#0C0C0C] font-medium uppercase tracking-widest px-8 py-3 sm:px-10 sm:py-3.5 text-sm sm:text-base hover:bg-[#0C0C0C]/10 transition-colors duration-200";

export default function LiveProjectButton({
  label = "Live Demo",
  href,
  tone = "light",
}: LiveProjectButtonProps) {
  const className = tone === "dark" ? DARK_CLASS : LIGHT_CLASS;

  if (href) {
    return (
      <a href={href} target="_blank" rel="noreferrer" className={className}>
        {label}
      </a>
    );
  }
  return <button className={className}>{label}</button>;
}
