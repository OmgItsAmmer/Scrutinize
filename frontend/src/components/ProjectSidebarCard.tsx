import { useState } from "react";
import type { ConversationItem, UserProject } from "../types/api";
import { IconTrash } from "./icons";
import { RonaldoProjectIcon } from "./RonaldoProjectIcon";

const INITIAL_CHAT_COUNT = 5;

type ProjectSidebarCardProps = {
  project: UserProject;
  selected: boolean;
  chats: ConversationItem[];
  chatsLoading: boolean;
  activeConversationId: string | null;
  deletingProjectId: string | null;
  deletingChatId: string | null;
  onHover: () => void;
  onSelectProject: () => void;
  onOpenChat: (conversationId: string | null) => void;
  onDeleteProject: (projectId: string) => void;
  onDeleteChat: (projectId: string, conversationId: string) => void;
};

export function ProjectSidebarCard({
  project,
  selected,
  chats,
  chatsLoading,
  activeConversationId,
  deletingProjectId,
  deletingChatId,
  onHover,
  onSelectProject,
  onOpenChat,
  onDeleteProject,
  onDeleteChat,
}: ProjectSidebarCardProps) {
  const [showAllChats, setShowAllChats] = useState(false);
  const visibleChats = showAllChats ? chats : chats.slice(0, INITIAL_CHAT_COUNT);
  const hasMoreChats = chats.length > INITIAL_CHAT_COUNT && !showAllChats;
  const deletingProject = deletingProjectId === project.project_id;

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
        <div className="project-hover-card__hero">
          <button
            type="button"
            onClick={onSelectProject}
            className="project-hover-card__hero-button"
            aria-label={`Open project ${project.name}`}
          >
            <RonaldoProjectIcon className="project-hover-card__image" />
            <div className="project-hover-card__hero-overlay" />
            <h3 className="project-hover-card__hero-title">{project.name}</h3>
          </button>
          <button
            type="button"
            className="project-hover-card__delete"
            aria-label={`Delete project ${project.name}`}
            title="Delete project"
            disabled={deletingProject}
            onClick={() => onDeleteProject(project.project_id)}
          >
            <IconTrash className="h-3.5 w-3.5" />
          </button>
        </div>

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
              const deletingChat = deletingChatId === chat.id;
              return (
                <div key={chat.id} className="project-hover-card__chat-row" role="listitem">
                  <button
                    type="button"
                    onClick={() => onOpenChat(chat.id)}
                    className={`project-hover-card__chat-tile ${chatActive ? "project-hover-card__chat-tile--active" : ""}`}
                    title={chat.title}
                  >
                    <span className="truncate">{chat.title}</span>
                  </button>
                  <button
                    type="button"
                    className="project-hover-card__chat-delete"
                    aria-label={`Delete chat ${chat.title}`}
                    title="Delete chat"
                    disabled={deletingChat}
                    onClick={() => onDeleteChat(project.project_id, chat.id)}
                  >
                    <IconTrash className="h-3 w-3" />
                  </button>
                </div>
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
