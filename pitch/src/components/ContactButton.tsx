interface ContactButtonProps {
  label?: string;
  href?: string;
  className?: string;
}

const CLASS =
  "inline-block rounded-full text-white font-medium uppercase tracking-widest px-8 py-3 sm:px-10 sm:py-3.5 md:px-12 md:py-4 text-xs sm:text-sm md:text-base transition-transform duration-200 hover:scale-[1.03]";

const STYLE = {
  background:
    "linear-gradient(123deg, #18011F 7%, #B600A8 37%, #7621B0 72%, #BE4C00 100%)",
  boxShadow: "0px 4px 4px rgba(181, 1, 167, 0.25), 4px 4px 12px #7721B1 inset",
  outline: "2px solid white",
  outlineOffset: "-3px",
} as const;

export default function ContactButton({
  label = "Contact Me",
  href,
  className = "",
}: ContactButtonProps) {
  if (href) {
    return (
      <a
        href={href}
        target="_blank"
        rel="noreferrer"
        className={`${CLASS} ${className}`}
        style={STYLE}
      >
        {label}
      </a>
    );
  }
  return (
    <button className={`${CLASS} ${className}`} style={STYLE}>
      {label}
    </button>
  );
}
