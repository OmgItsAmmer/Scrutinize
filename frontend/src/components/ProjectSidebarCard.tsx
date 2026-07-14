import { useState } from "react";
import type { ConversationItem, UserProject } from "../types/api";
import { RonaldoProjectIcon } from "./RonaldoProjectIcon";

const INITIAL_CHAT_COUNT = 5;

type ProjectSidebarCardProps = {
  project: UserProject;
  selected: boolean;
  chats: ConversationItem[];
  chatsLoading: boolean;
  activeConversationId: string | null;
  onHover: () => void;
  onSelectProject: () => void;
  onOpenChat: (conversationId: string | null) => void;
};

export function ProjectSidebarCard({
  project,
  selected,
  chats,
  chatsLoading,
  activeConversationId,
  onHover,
  onSelectProject,
  onOpenChat,
}: ProjectSidebarCardProps) {
  const [showAllChats, setShowAllChats] = useState(false);
  const visibleChats = showAllChats ? chats : chats.slice(0, INITIAL_CHAT_COUNT);
  const hasMoreChats = chats.length > INITIAL_CHAT_COUNT && !showAllChats;

  return (
    <article
      className={`project-hover-card group ${selected ? "project-hover-card--selected" : ""}`}
      onMouseEnter={onHover}
      onFocusCapture={onHover}
    >
      <button
        type="button"
        onClick={onSelectProject}
        className="project-hover-card__collapsed"
        aria-label={`Open project ${project.name}`}
      >
        <span className="truncate">{project.name}</span>
      </button>

      <div className="project-hover-card__expanded">
        <div className="project-hover-card__expanded-inner">
        <button
          type="button"
          onClick={onSelectProject}
          className="project-hover-card__hero"
          aria-label={`Open project ${project.name}`}
        >
          <RonaldoProjectIcon className="project-hover-card__image" />
          <div className="project-hover-card__hero-overlay" />
          <h3 className="project-hover-card__hero-title">{project.name}</h3>
        </button>

        <div className="project-hover-card__panel">
          <p className="project-hover-card__chats-label">Recent chats</p>

          <div className="project-hover-card__chats" role="list">
            {chatsLoading && (
              <p className="project-hover-card__status">Loading chats...</p>
            )}
            {!chatsLoading && chats.length === 0 && (
              <button
                type="button"
                onClick={() => onOpenChat(null)}
                className="project-hover-card__chat-tile"
              >
                Start your first chat
              </button>
            )}
            {visibleChats.map((chat) => {
              const chatActive = activeConversationId === chat.id && selected;
              return (
                <button
                  key={chat.id}
                  type="button"
                  role="listitem"
                  onClick={() => onOpenChat(chat.id)}
                  className={`project-hover-card__chat-tile ${chatActive ? "project-hover-card__chat-tile--active" : ""}`}
                  title={chat.title}
                >
                  <span className="truncate">{chat.title}</span>
                </button>
              );
            })}
            {hasMoreChats && (
              <button
                type="button"
                onClick={() => setShowAllChats(true)}
                className="project-hover-card__show-more"
              >
                Show more
              </button>
            )}
          </div>

          <button
            type="button"
            onClick={() => onOpenChat(null)}
            className="project-hover-card__cta"
          >
            New chat
          </button>
        </div>
        </div>
      </div>
    </article>
  );
}
