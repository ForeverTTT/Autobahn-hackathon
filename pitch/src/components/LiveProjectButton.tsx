interface LiveProjectButtonProps {
  label?: string;
  href?: string;
}

const CLASS =
  "inline-block rounded-full border-2 border-[#D7E2EA] text-[#D7E2EA] font-medium uppercase tracking-widest px-8 py-3 sm:px-10 sm:py-3.5 text-sm sm:text-base hover:bg-[#D7E2EA]/10 transition-colors duration-200";

export default function LiveProjectButton({
  label = "Live Demo",
  href,
}: LiveProjectButtonProps) {
  if (href) {
    return (
      <a href={href} target="_blank" rel="noreferrer" className={CLASS}>
        {label}
      </a>
    );
  }
  return <button className={CLASS}>{label}</button>;
}
