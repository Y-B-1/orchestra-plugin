export function Loading({ label = "Loading" }: { label?: string }) {
  return (
    <p className="feedback" role="status">
      {label}...
    </p>
  );
}

export function ErrorState({ error, onRetry }: { error: Error; onRetry?: () => void }) {
  return (
    <p className="feedback feedback--error" role="alert">
      Something went wrong: {error.message}
      {onRetry ? (
        <>
          {" "}
          <button type="button" className="button button--small feedback__retry" onClick={onRetry}>
            Try again
          </button>
        </>
      ) : null}
    </p>
  );
}

export function EmptyState({ message }: { message: string }) {
  return <p className="feedback feedback--empty">{message}</p>;
}
