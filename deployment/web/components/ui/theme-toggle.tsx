"use client";

import React, { useEffect, useState } from "react";
import { useTheme } from "../theme-provider";
import { Sun, Moon } from "lucide-react";

export function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return (
      <div className="w-16 h-7 rounded border border-terminal-border bg-terminal-panel opacity-50"></div>
    );
  }

  return (
    <button
      onClick={toggleTheme}
      type="button"
      className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-mono font-medium rounded border border-terminal-border bg-terminal-panel hover:bg-terminal-secondary text-terminal-primary transition-colors focus:outline-none"
      title={`Switch to ${theme === "dark" ? "Light" : "Dark"} Mode (Shift+T)`}
      aria-label="Toggle theme"
    >
      {theme === "dark" ? (
        <>
          <Moon className="w-3.5 h-3.5 text-terminal-muted" />
          <span className="uppercase tracking-wider">DARK</span>
        </>
      ) : (
        <>
          <Sun className="w-3.5 h-3.5 text-amber-500" />
          <span className="uppercase tracking-wider">LIGHT</span>
        </>
      )}
    </button>
  );
}

