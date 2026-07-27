import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { IconX } from "./icons";

export type ConfirmTone = "default" | "danger";

export type ConfirmOptions = {
  title: string;
  description: string;
  confirmLabel?: string;
  cancelLabel?: string;
  tone?: ConfirmTone;
};

type ConfirmRequest = ConfirmOptions & {
  resolve: (value: boolean) => void;
};

type ConfirmContextValue = {
  confirm: (options: ConfirmOptions) => Promise<boolean>;
};

const ConfirmContext = createContext<ConfirmContextValue | null>(null);

function ConfirmDialog({
  request,
  onClose,
}: {
  request: ConfirmRequest;
  onClose: (confirmed: boolean) => void;
}) {
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose(false);
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  const confirmLabel = request.confirmLabel ?? (request.tone === "danger" ? "Delete" : "Confirm");
  const cancelLabel = request.cancelLabel ?? "Cancel";
  const confirmButtonClass = "app-btn bg-black text-white hover:bg-zinc-800 transition-colors";

  return (
    <div
      className="confirm-dialog-overlay"
      onClick={() => onClose(false)}
      role="presentation"
    >
      <div
        className="confirm-dialog bg-white border border-zinc-200 shadow-2xl"
        onClick={(event) => event.stopPropagation()}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
        aria-describedby="confirm-dialog-description"
      >
        <div className="confirm-dialog__header">
          <h2 id="confirm-dialog-title" className="confirm-dialog__title">
            {request.title}
          </h2>
          <button
            type="button"
            className="confirm-dialog__close"
            aria-label="Close dialog"
            onClick={() => onClose(false)}
          >
            <IconX className="h-4 w-4" />
          </button>
        </div>
        <p id="confirm-dialog-description" className="confirm-dialog__description">
          {request.description}
        </p>
        <div className="confirm-dialog__actions">
          <button type="button" className="app-btn border border-black text-black bg-white hover:bg-zinc-50 transition-colors" onClick={() => onClose(false)}>
            {cancelLabel}
          </button>
          <button type="button" className={confirmButtonClass} onClick={() => onClose(true)}>
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

export function ConfirmDialogProvider({ children }: { children: ReactNode }) {
  const [request, setRequest] = useState<ConfirmRequest | null>(null);

  const confirm = useCallback((options: ConfirmOptions) => {
    return new Promise<boolean>((resolve) => {
      setRequest({ ...options, resolve });
    });
  }, []);

  const close = useCallback((confirmed: boolean) => {
    setRequest((current) => {
      current?.resolve(confirmed);
      return null;
    });
  }, []);

  const value = useMemo(() => ({ confirm }), [confirm]);

  return (
    <ConfirmContext.Provider value={value}>
      {children}
      {request ? <ConfirmDialog request={request} onClose={close} /> : null}
    </ConfirmContext.Provider>
  );
}

export function useConfirm() {
  const context = useContext(ConfirmContext);
  if (!context) {
    throw new Error("useConfirm must be used within ConfirmDialogProvider");
  }
  return context.confirm;
}
