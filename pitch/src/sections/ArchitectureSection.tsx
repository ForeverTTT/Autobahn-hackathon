import { motion } from "framer-motion";
import FadeIn from "../components/FadeIn";

const boxVariants = {
  hidden: { opacity: 0, x: -50 },
  visible: { opacity: 1, x: 0 },
};

const arrowVariants = {
  hidden: { opacity: 0, scale: 0 },
  visible: { opacity: 1, scale: 1 },
};

export default function ArchitectureSection() {
  return (
    <section
      id="architecture"
      className="relative z-10 -mt-10 sm:-mt-12 md:-mt-14 bg-white rounded-t-[40px] sm:rounded-t-[50px] md:rounded-t-[60px] px-5 sm:px-8 md:px-10 py-20 sm:py-24 md:py-32"
    >
      <FadeIn
        as="h2"
        delay={0}
        y={40}
        className="text-[#0C0C0C] font-black uppercase leading-none tracking-tight text-center mb-10 sm:mb-12 md:mb-16"
        style={{ fontSize: "clamp(3rem, 11vw, 150px)" }}
      >
        Project Architecture
      </FadeIn>

      <div className="mx-auto flex max-w-6xl flex-col items-center">
        <FadeIn delay={0.1} y={20}>
          <p
            className="mb-12 text-center font-medium text-[#0C0C0C]/55"
            style={{ fontSize: "clamp(1rem, 1.6vw, 1.35rem)" }}
          >
            AI-native traffic flow prediction platform
          </p>
        </FadeIn>

        {/* Horizontal Architecture Diagram */}
        <div className="w-full flex flex-col md:flex-row items-center justify-center gap-5 md:gap-6">
          {/* Data Layer */}
          <motion.div
            variants={boxVariants}
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
            transition={{ duration: 0.5, delay: 0.2 }}
            className="w-full md:w-auto md:flex-1 max-w-[280px] bg-[#f8f9fa] rounded-3xl p-8 text-center border border-[#e0e0e0] shadow-sm"
          >
            <span className="inline-block px-5 py-2 rounded-full border border-[#ccc] text-sm font-semibold text-[#555] uppercase tracking-wider mb-4">
              Data
            </span>
            <h4 className="text-[#1a1a1a] font-bold text-xl md:text-2xl">
              Data Processing Layer
            </h4>
          </motion.div>

          {/* Arrow */}
          <motion.div
            variants={arrowVariants}
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
            transition={{ duration: 0.3, delay: 0.4 }}
            className="text-[#5b7fff] text-4xl font-light rotate-90 md:rotate-0 select-none"
          >
            →
          </motion.div>

          {/* Model Layer */}
          <motion.div
            variants={boxVariants}
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
            transition={{ duration: 0.5, delay: 0.5 }}
            className="w-full md:w-auto md:flex-1 max-w-[280px] bg-[#f8f9fa] rounded-3xl p-8 text-center border border-[#e0e0e0] shadow-sm"
          >
            <span className="inline-block px-5 py-2 rounded-full border border-[#ccc] text-sm font-semibold text-[#555] uppercase tracking-wider mb-4">
              Model
            </span>
            <h4 className="text-[#1a1a1a] font-bold text-xl md:text-2xl">
              Model<br />Layer
            </h4>
          </motion.div>

          {/* Arrow */}
          <motion.div
            variants={arrowVariants}
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
            transition={{ duration: 0.3, delay: 0.7 }}
            className="text-[#5b7fff] text-4xl font-light rotate-90 md:rotate-0 select-none"
          >
            →
          </motion.div>

          {/* Agent Layer */}
          <motion.div
            variants={boxVariants}
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
            transition={{ duration: 0.5, delay: 0.8 }}
            className="w-full md:w-auto md:flex-1 max-w-[280px] bg-[#f8f9fa] rounded-3xl p-8 text-center border border-[#e0e0e0] shadow-sm"
          >
            <span className="inline-block px-5 py-2 rounded-full border border-[#ccc] text-sm font-semibold text-[#555] uppercase tracking-wider mb-4">
              Agent
            </span>
            <h4 className="text-[#1a1a1a] font-bold text-xl md:text-2xl">
              AI Agent Layer
            </h4>
          </motion.div>

          {/* Arrow */}
          <motion.div
            variants={arrowVariants}
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
            transition={{ duration: 0.3, delay: 1.0 }}
            className="text-[#5b7fff] text-4xl font-light rotate-90 md:rotate-0 select-none"
          >
            →
          </motion.div>

          {/* Frontend Layer */}
          <motion.div
            variants={boxVariants}
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
            transition={{ duration: 0.5, delay: 1.1 }}
            className="w-full md:w-auto md:flex-1 max-w-[280px] bg-[#f8f9fa] rounded-3xl p-8 text-center border border-[#e0e0e0] shadow-sm"
          >
            <span className="inline-block px-5 py-2 rounded-full border border-[#ccc] text-sm font-semibold text-[#555] uppercase tracking-wider mb-4">
              Frontend
            </span>
            <h4 className="text-[#1a1a1a] font-bold text-xl md:text-2xl">
              Frontend Interaction Layer
            </h4>
          </motion.div>
        </div>
      </div>
    </section>
  );
}
