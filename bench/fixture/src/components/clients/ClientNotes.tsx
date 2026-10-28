import { useId, useState, type FormEvent } from "react";
import { useLocalStorage } from "../../hooks/useLocalStorage";
import type { ClientNote } from "../../types";
import { formatDateTime } from "../../utils/format";
import { createId } from "../../utils/ids";
import { EmptyState } from "../Feedback";

export const NOTE_MAX_LENGTH = 500;

export function notesKey(clientId: string): string {
  return `pulse.client-notes.${clientId}`;
}

interface ClientNotesProps {
  clientId: string;
  author?: string;
  /** Injected in tests; defaults to the current time. */
  now?: () => Date;
}

export function ClientNotes({ clientId, author = "Dana Whitaker", now = () => new Date() }: ClientNotesProps) {
  const [notes, setNotes] = useLocalStorage<ClientNote[]>(notesKey(clientId), []);
  const [draft, setDraft] = useState("");
  const fieldId = useId();
  const trimmed = draft.trim();

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!trimmed) return;
    const note: ClientNote = { id: createId("note"), text: trimmed, author, createdAt: now().toISOString() };
    setNotes((prev) => [note, ...prev]);
    setDraft("");
  }

  function remove(id: string) {
    setNotes((prev) => prev.filter((note) => note.id !== id));
  }

  return (
    <section className="client-notes" aria-label="Client notes">
      <form className="client-notes__form" onSubmit={submit}>
        <label htmlFor={fieldId} className="client-notes__label">
          New note
        </label>
        <textarea
          id={fieldId}
          className="input client-notes__input"
          rows={3}
          maxLength={NOTE_MAX_LENGTH}
          value={draft}
          placeholder="Call summary, follow-ups, preferences..."
          onChange={(event) => setDraft(event.target.value)}
        />
        <div className="client-notes__actions">
          <span className="client-notes__count">
            {draft.length}/{NOTE_MAX_LENGTH}
          </span>
          <button type="submit" className="button button--primary" disabled={!trimmed}>
            Add note
          </button>
        </div>
      </form>
      {notes.length === 0 ? (
        <EmptyState message="No notes yet." />
      ) : (
        <ol className="client-notes__list">
          {notes.map((note) => (
            <li key={note.id} className="client-notes__item">
              <p className="client-notes__text">{note.text}</p>
              <p className="client-notes__meta">
                {note.author}, <time dateTime={note.createdAt}>{formatDateTime(note.createdAt)} UTC</time>
                <button
                  type="button"
                  className="client-notes__delete"
                  onClick={() => remove(note.id)}
                  aria-label={`Delete note from ${formatDateTime(note.createdAt)}`}
                >
                  Delete
                </button>
              </p>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
