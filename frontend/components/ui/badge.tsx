import * as React from "react";
import { cn } from "@/lib/utils";

const variants = {
  default: "border-transparent bg-primary/15 text-primary",
  success: "border-emerald-500/30 bg-emerald-500/15 text-emerald-300",
  warning: "border-amber-500/30 bg-amber-500/15 text-amber-300",
  destructive: "border-red-500/30 bg-red-500/15 text-red-300",
  muted: "border-border bg-muted text-muted-foreground",
};

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  readonly variant?: keyof typeof variants;
}

export function Badge({ className, variant = "default", ...props }: BadgeProps): JSX.Element {
  return (
    <span
      className={cn(
        "inline-flex h-6 items-center rounded-md border px-2 text-xs font-medium",
        variants[variant],
        className,
      )}
      {...props}
    />
  );
}
