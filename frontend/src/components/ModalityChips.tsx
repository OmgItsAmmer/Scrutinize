import type { ComponentType, SVGProps } from "react";
import type { ModalityFilter } from "../types/api";
import { IconDocument, IconFilm, IconGrid, IconWaveform } from "./icons";

const FILTERS: {
  id: ModalityFilter;
  label: string;
  icon: ComponentType<SVGProps<SVGSVGElement>>;
  badgeColor: string;
}[] = [
  { id: "all", label: "All", icon: IconGrid, badgeColor: "var(--chatly-badge-all)" },
  { id: "text", label: "Text", icon: IconDocument, badgeColor: "var(--chatly-badge-text)" },
  { id: "audio", label: "Audio", icon: IconWaveform, badgeColor: "var(--chatly-badge-audio)" },
  { id: "video", label: "Video", icon: IconFilm, badgeColor: "var(--chatly-badge-video)" },
];

type ModalityChipsProps = {
  value: ModalityFilter;
  onChange: (value: ModalityFilter) => void;
  disabled?: boolean;
};

export function ModalityChips({ value, onChange, disabled }: ModalityChipsProps) {
  return (
    <div className="flex flex-wrap items-start justify-center gap-6 sm:gap-8">
      {FILTERS.map((filter) => {
        const Icon = filter.icon;
        const active = value === filter.id;

        return (
          <button
            key={filter.id}
            type="button"
            disabled={disabled}
            onClick={() => onChange(filter.id)}
            className={`group flex w-[72px] flex-col items-center gap-2.5 transition disabled:opacity-50 ${
              active ? "opacity-100" : "opacity-80 hover:opacity-100"
            }`}
          >
            <span
              className={`flex h-12 w-12 items-center justify-center rounded-full text-white shadow-sm transition ${
                active ? "scale-105 ring-2 ring-white ring-offset-2" : "group-hover:scale-105"
              }`}
              style={{
                backgroundColor: filter.badgeColor,
                ...(active ? { boxShadow: `0 0 0 2px ${filter.badgeColor}` } : {}),
              }}
            >
              <Icon className="h-5 w-5" />
            </span>
            <span
              className={`text-xs font-medium transition ${
                active
                  ? "text-[var(--chatly-text-primary)]"
                  : "text-[var(--chatly-text-secondary)]"
              }`}
            >
              {filter.label}
            </span>
          </button>
        );
      })}
    </div>
  );
}
