/**
 * Styled <button>. Three variants — primary, secondary, ghost — plus a
 * loading state that disables the button and shows a spinner.
 *
 * Component is a thin wrapper over the native button; props pass
 * through so callers can attach `type`, `aria-*`, `onClick`, etc.
 */

import * as React from "react";

import { cn } from "@/lib/cn";

type Variant = "primary" | "secondary" | "ghost";

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  loading?: boolean;
};

const VARIANTS: Record<Variant, string> = {
  primary:
    "bg-neutral-100 text-neutral-950 hover:bg-white disabled:bg-neutral-700 disabled:text-neutral-400",
  secondary:
    "bg-neutral-800 text-neutral-100 hover:bg-neutral-700 disabled:bg-neutral-900 disabled:text-neutral-500",
  ghost:
    "bg-transparent text-neutral-300 hover:bg-neutral-900 disabled:text-neutral-600",
};

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  function Button(
    { className, variant = "primary", loading = false, disabled, children, ...rest },
    ref,
  ) {
    return (
      <button
        ref={ref}
        disabled={disabled || loading}
        aria-busy={loading || undefined}
        className={cn(
          "inline-flex items-center justify-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition-colors disabled:cursor-not-allowed",
          VARIANTS[variant],
          className,
        )}
        {...rest}
      >
        {loading && <Spinner />}
        <span>{children}</span>
      </button>
    );
  },
);

function Spinner() {
  return (
    <span
      role="presentation"
      className="inline-block size-3 animate-spin rounded-full border-2 border-current border-t-transparent"
    />
  );
}
