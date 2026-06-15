import { useEffect, useState } from "react";

const EXAMPLE_QUERIES = [
  "What did the team discuss in last week's meeting?",
  "Find mentions of the product roadmap in my documents…",
  "Summarize key points from my audio recordings…",
  "Which videos mention the quarterly budget?",
  "Search for onboarding notes across all content…",
];

type AnimatedPlaceholderProps = {
  paused: boolean;
};

export function AnimatedPlaceholder({ paused }: AnimatedPlaceholderProps) {
  const [queryIndex, setQueryIndex] = useState(0);
  const [displayText, setDisplayText] = useState("");
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    if (paused) {
      return;
    }

    const currentQuery = EXAMPLE_QUERIES[queryIndex];

    const timeout = setTimeout(
      () => {
        if (!isDeleting) {
          const next = currentQuery.slice(0, displayText.length + 1);
          setDisplayText(next);
          if (next === currentQuery) {
            setTimeout(() => setIsDeleting(true), 1800);
          }
        } else {
          const next = currentQuery.slice(0, displayText.length - 1);
          setDisplayText(next);
          if (next === "") {
            setIsDeleting(false);
            setQueryIndex((index) => (index + 1) % EXAMPLE_QUERIES.length);
          }
        }
      },
      isDeleting ? 24 : displayText.length === currentQuery.length ? 0 : 42,
    );

    return () => clearTimeout(timeout);
  }, [displayText, isDeleting, paused, queryIndex]);

  return (
    <span className="pointer-events-none absolute inset-0 flex items-start pt-1 text-[15px] text-[var(--chatly-text-muted)]">
      {displayText}
      <span className="ml-0.5 inline-block h-[1.1em] w-0.5 animate-pulse bg-[var(--chatly-text-muted)]" />
    </span>
  );
}
