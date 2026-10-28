import { useId } from "react";

interface ToggleProps {
  label: string;
  description?: string;
  checked: boolean;
  onChange: (next: boolean) => void;
}

export function Toggle({ label, description, checked, onChange }: ToggleProps) {
  const id = useId();
  return (
    <div className="toggle">
      <div className="toggle__text">
        <label htmlFor={id} className="toggle__label">
          {label}
        </label>
        {description ? <p className="toggle__description">{description}</p> : null}
      </div>
      <input
        id={id}
        type="checkbox"
        role="switch"
        className="toggle__input"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
      />
    </div>
  );
}
