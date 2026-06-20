import { CSSProperties, useRef } from "react";
import { motion, MotionValue, useScroll, useTransform } from "framer-motion";

interface AnimatedTextProps {
  text: string;
  className?: string;
  style?: CSSProperties;
}

function Char({
  char,
  range,
  progress,
}: {
  char: string;
  range: [number, number];
  progress: MotionValue<number>;
}) {
  const opacity = useTransform(progress, range, [0.2, 1]);
  return (
    <span className="relative inline-block whitespace-pre">
      {/* invisible placeholder holds the layout width */}
      <span className="opacity-0">{char}</span>
      {/* animated copy fades from 0.2 -> 1 as it scrolls into the reveal band */}
      <motion.span className="absolute left-0 top-0" style={{ opacity }}>
        {char}
      </motion.span>
    </span>
  );
}

/**
 * Character-by-character scroll reveal. Each glyph brightens as the paragraph
 * passes through the [start 0.8, end 0.2] scroll band.
 */
export default function AnimatedText({ text, className, style }: AnimatedTextProps) {
  const ref = useRef<HTMLParagraphElement>(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start 0.8", "end 0.2"],
  });

  const chars = text.split("");
  const total = chars.length;

  return (
    <p ref={ref} className={className} style={style}>
      {chars.map((char, i) => {
        const start = i / total;
        const end = (i + 1) / total;
        return <Char key={i} char={char} range={[start, end]} progress={scrollYProgress} />;
      })}
    </p>
  );
}
