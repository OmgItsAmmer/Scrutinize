import { useEffect } from "react";
import { useApp } from "../context/AppContext";
import { ConversationChatView } from "./ConversationChatView";
import { LibraryView } from "./LibraryView";
import { ProjectSettingsView } from "./SettingsView";
import { UploadView } from "./UploadView";
import { ProjectTabs, type ProjectChoice } from "./ProjectTabs";

export function ProjectWorkspace() {
  const { state, refreshLibrary, setProjectChoice } = useApp();
  const choice = state.projectChoice as ProjectChoice;

  useEffect(() => {
    if (choice === "library") void refreshLibrary();
  }, [choice, refreshLibrary, state.project?.projectId]);

  return (
    <section className="flex h-full min-h-0 flex-col">
      <ProjectTabs choice={choice} onChoiceChange={setProjectChoice} />
      <div className="min-h-0 flex-1">
        {choice === "chats" && <ConversationChatView scope="project" />}
        {choice === "sources" && <UploadView />}
        {choice === "library" && <LibraryView />}
        {choice === "settings" && <ProjectSettingsView />}
      </div>
    </section>
  );
}
