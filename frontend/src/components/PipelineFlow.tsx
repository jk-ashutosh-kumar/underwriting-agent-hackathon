import { motion, AnimatePresence } from "framer-motion"
import { cn } from "@/lib/utils"
import {
  CheckCircle2,
  MinusCircle,
  FileSearch,
  Cpu,
  GitBranch,
  UserCheck,
  Play,
  Scale,
  ShieldCheck,
} from "lucide-react"

export const PIPELINE_STEPS = [
  {
    id: "ingesting",
    label: "Ingest",
    sublabel: "Parsing documents",
    icon: FileSearch,
  },
  {
    id: "analysis",
    label: "Committee",
    sublabel: "Agents deliberating",
    icon: Cpu,
  },
  { id: "router", label: "Router", sublabel: "Routing query", icon: GitBranch },
  { id: "hitl", label: "HITL", sublabel: "Human review", icon: UserCheck },
  { id: "resume", label: "Resume", sublabel: "Continuing flow", icon: Play },
  { id: "deciding", label: "Decision", sublabel: "Final verdict", icon: Scale },
  {
    id: "checkpoint",
    label: "Checkpoint",
    sublabel: "Saving state",
    icon: ShieldCheck,
  },
] as const

export type PipelineStepId = (typeof PIPELINE_STEPS)[number]["id"]
type StepStatus = "done" | "active" | "pending" | "skipped"

function stepStatus(
  i: number,
  activeIndex: number,
  done: boolean,
  skipped: Set<string>,
  id: string
): StepStatus {
  if (skipped.has(id)) return "skipped"
  if (done) return "done"
  if (i < activeIndex) return "done"
  if (i === activeIndex) return "active"
  return "pending"
}

/* ─────────────────────── Creative Scene Animations ───────────────────────── */

/** Scanner lines going over a document page */
function DocumentScannerScene() {
  return (
    <div className="relative mx-auto h-52 w-44">
      {/* Paper */}
      <div className="absolute inset-0 overflow-hidden rounded-lg border border-border/60 bg-card shadow-xl">
        {/* Text lines on doc */}
        {[0.15, 0.28, 0.41, 0.54, 0.67, 0.8].map((top, i) => (
          <div
            key={i}
            className="absolute right-4 left-4 h-[3px] rounded-full bg-border/50"
            style={{ top: `${top * 100}%` }}
          />
        ))}
        {/* Scanner beam */}
        <motion.div
          className="absolute right-0 left-0 h-[3px] bg-gradient-to-r from-transparent via-primary to-transparent opacity-80"
          animate={{ top: ["8%", "90%", "8%"] }}
          transition={{ duration: 2.5, repeat: Infinity, ease: "easeInOut" }}
          style={{ position: "absolute" }}
        />
        {/* Highlight sweep */}
        <motion.div
          className="pointer-events-none absolute right-0 left-0 h-8 bg-gradient-to-b from-primary/10 to-transparent"
          animate={{ top: ["4%", "82%", "4%"] }}
          transition={{ duration: 2.5, repeat: Infinity, ease: "easeInOut" }}
        />
      </div>

      {/* Eye cursor */}
      <motion.div
        className="absolute -right-8 flex h-6 w-6 items-center justify-center rounded-full border border-primary/40 bg-primary/20"
        animate={{ top: ["10%", "85%", "10%"] }}
        transition={{ duration: 2.5, repeat: Infinity, ease: "easeInOut" }}
      >
        <div className="h-2 w-2 animate-pulse rounded-full bg-primary" />
      </motion.div>
    </div>
  )
}

/** Agents communicating — a cluster of nodes with traveling data pulses */
function CommitteeScene() {
  const agents = [
    { label: "Auditor", color: "bg-red-500", angle: -120 },
    { label: "Trend", color: "bg-emerald-600", angle: 0 },
    { label: "Benchmark", color: "bg-[#013b2e]", angle: 120 },
  ]
  const R = 100 // radius

  return (
    <div className="relative mx-auto flex h-52 w-52 items-center justify-center">
      {/* Center hub */}
      <div className="absolute z-10 flex h-12 w-12 items-center justify-center rounded-full border-2 border-accent/40 bg-accent/10">
        <motion.div
          className="h-4 w-4 rounded-full bg-accent"
          animate={{ scale: [1, 1.3, 1], opacity: [0.7, 1, 0.7] }}
          transition={{ duration: 1.6, repeat: Infinity }}
        />
      </div>

      {/* Agent nodes + pulse lines */}
      {agents.map((agent, i) => {
        const rad = (agent.angle * Math.PI) / 180
        const x = Math.cos(rad) * R
        const y = Math.sin(rad) * R

        return (
          <div key={i}>
            {/* Line from center */}
            <svg
              className="pointer-events-none absolute inset-0 h-full w-full"
              style={{ zIndex: 0 }}
            >
              <line
                x1="50%"
                y1="50%"
                x2={`calc(50% + ${x}px)`}
                y2={`calc(50% + ${y}px)`}
                stroke="var(--border)"
                strokeWidth="1"
                strokeDasharray="4 3"
              />
            </svg>

            {/* Traveling pulse */}
            <motion.div
              className="absolute h-2.5 w-2.5 rounded-full bg-accent opacity-80 blur-[1px]"
              style={{ left: "50%", top: "50%", marginLeft: -5, marginTop: -5 }}
              animate={{
                x: [0, x, 0],
                y: [0, y, 0],
              }}
              transition={{
                duration: 2.0,
                repeat: Infinity,
                delay: i * 0.65,
                ease: "easeInOut",
              }}
            />

            {/* Agent node */}
            <motion.div
              className={cn(
                "absolute flex items-center justify-center rounded-full border-2 border-white/20 px-1 text-center text-[10px] font-bold text-white",
                agent.color + "/80"
              )}
              style={{
                width: 70,
                height: 70,
                left: `calc(50% + ${x}px - 28px)`,
                top: `calc(50% + ${y}px - 28px)`,
                zIndex: 10,
              }}
              animate={{ scale: [1, 1.08, 1] }}
              transition={{ duration: 2, repeat: Infinity, delay: i * 0.5 }}
            >
              {agent.label}
            </motion.div>
          </div>
        )
      })}
    </div>
  )
}

/** Generic animated icon for other steps */
function GenericScene({ icon: Icon, color }: { icon: any; color: string }) {
  return (
    <div className="mx-auto flex h-32 w-32 items-center justify-center">
      <motion.div
        className={cn(
          "flex h-20 w-20 items-center justify-center rounded-2xl border-2",
          color
        )}
        animate={{ scale: [1, 1.07, 1], opacity: [0.8, 1, 0.8] }}
        transition={{ duration: 1.8, repeat: Infinity }}
      >
        <motion.div
          animate={{ rotate: [0, 10, -10, 0] }}
          transition={{ duration: 2, repeat: Infinity }}
        >
          <Icon className="h-10 w-10" />
        </motion.div>
      </motion.div>
    </div>
  )
}

function getSceneForStep(stepId: string, icon: any) {
  if (stepId === "ingesting") return <DocumentScannerScene />
  if (stepId === "analysis") return <CommitteeScene />
  if (stepId === "deciding")
    return (
      <GenericScene
        icon={icon}
        color="border-success/40 bg-success/10 text-success"
      />
    )
  return (
    <GenericScene
      icon={icon}
      color="border-primary/40 bg-primary/10 text-primary"
    />
  )
}

/* ─────────────────────── Connector ─────────────────────── */
function FlowConnector({ active }: { active: boolean }) {
  return (
    <div className="relative mx-1 mt-[-20px] flex w-8 shrink-0 items-center sm:w-10">
      <div
        className={cn(
          "h-px w-full transition-colors duration-700",
          active ? "bg-primary/50" : "bg-border/40"
        )}
      />
      <AnimatePresence>
        {active && (
          <motion.div
            className="absolute top-1/2 h-2 w-2 -translate-y-1/2 rounded-full bg-primary blur-sm"
            animate={{ left: ["0%", "100%"], opacity: [0, 1, 0] }}
            transition={{ duration: 1.1, repeat: Infinity, ease: "easeInOut" }}
          />
        )}
      </AnimatePresence>
    </div>
  )
}

/* ─────────────────────── Step Pill ─────────────────────── */
function StepPill({
  step,
  status,
  index,
}: {
  step: (typeof PIPELINE_STEPS)[number]
  status: StepStatus
  index: number
}) {
  const Icon = step.icon
  return (
    <motion.div
      className="flex min-w-[56px] flex-col items-center gap-1.5"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.06, duration: 0.35 }}
    >
      <div className="relative">
        {status === "active" && (
          <motion.div
            className="absolute inset-0 rounded-full bg-primary"
            animate={{ scale: [1, 1.9], opacity: [0.45, 0] }}
            transition={{ duration: 1.2, repeat: Infinity }}
          />
        )}
        <div
          className={cn(
            "relative flex h-9 w-9 items-center justify-center rounded-full border-2 transition-all duration-500",
            status === "done" && "border-success bg-success/15 text-success",
            status === "active" && "border-primary bg-primary/20 text-primary",
            status === "pending" &&
              "border-border/50 bg-muted/30 text-muted-foreground/40",
            status === "skipped" &&
              "border-border/30 bg-muted/20 text-muted-foreground/30"
          )}
        >
          {status === "done" ? (
            <CheckCircle2 className="h-4 w-4" />
          ) : status === "skipped" ? (
            <MinusCircle className="h-4 w-4" />
          ) : (
            <Icon
              className={cn("h-4 w-4", status === "active" && "animate-pulse")}
            />
          )}
        </div>
      </div>

      <span
        className={cn(
          "text-[9px] font-semibold tracking-widest uppercase",
          status === "done" && "text-success",
          status === "active" && "text-primary",
          status === "pending" && "text-muted-foreground/30",
          status === "skipped" && "text-muted-foreground/30 line-through"
        )}
      >
        {step.label}
      </span>
    </motion.div>
  )
}

/* ─────────────────────── Main Component ─────────────────────── */
export interface PipelineFlowProps {
  activeIndex: number
  skippedStepIds?: string[]
  done?: boolean
  progressLabel?: string | null
}

export function PipelineFlow({
  activeIndex,
  skippedStepIds = [],
  done = false,
  progressLabel,
}: PipelineFlowProps) {
  if (activeIndex < 0) return null

  const skipped = new Set(skippedStepIds)
  const activeStep = PIPELINE_STEPS[activeIndex]

  return (
    <AnimatePresence>
      {!done && (
        /* ── Fullscreen overlay ── */
        <motion.div
          key="pipeline-overlay"
          className="fixed inset-0 z-40 flex items-center justify-center bg-background/90 backdrop-blur-sm"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0, scale: 0.97 }}
          transition={{ duration: 0.4, ease: "easeInOut" }}
        >
          <div className="flex w-full max-w-2xl flex-col items-center gap-8 px-6">
            {/* ── Creative scene ── */}
            <motion.div
              key={activeStep?.id}
              initial={{ opacity: 0, scale: 0.88, y: 12 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.88 }}
              transition={{ duration: 0.45 }}
              className="flex flex-col items-center gap-4"
            >
              <div className="flex h-56 items-center justify-center">
                {activeStep && getSceneForStep(activeStep.id, activeStep.icon)}
              </div>
              <div className="space-y-1 text-center">
                <p className="text-[10px] font-semibold tracking-[0.25em] text-muted-foreground/50 uppercase">
                  Step {activeIndex + 1} of {PIPELINE_STEPS.length}
                </p>
                <h2 className="text-2xl font-bold text-foreground">
                  {activeStep?.sublabel ?? "Processing..."}
                </h2>
                {progressLabel && (
                  <motion.p
                    key={progressLabel}
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="mt-1 max-w-md truncate font-mono text-sm text-muted-foreground"
                    title={progressLabel}
                  >
                    {progressLabel}
                  </motion.p>
                )}
              </div>
            </motion.div>

            {/* ── Step pills progress ── */}
            <div className="flex flex-wrap items-center justify-center gap-y-3">
              {PIPELINE_STEPS.map((step, idx) => {
                const status = stepStatus(
                  idx,
                  activeIndex,
                  done,
                  skipped,
                  step.id
                )
                const connectorActive = status === "done" || status === "active"
                return (
                  <div key={step.id} className="flex items-center">
                    <StepPill step={step} status={status} index={idx} />
                    {idx < PIPELINE_STEPS.length - 1 && (
                      <FlowConnector active={connectorActive} />
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
