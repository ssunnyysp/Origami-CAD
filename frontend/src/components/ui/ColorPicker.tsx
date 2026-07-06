import { useAppStore } from "../../store/useAppStore";

export function ColorPicker() {
  const paperColor = useAppStore((s) => s.paperColor);
  const setPaperColor = useAppStore((s) => s.setPaperColor);

  return (
    <label className="control-row">
      <span>Paper color</span>
      <input type="color" value={paperColor} onChange={(e) => setPaperColor(e.target.value)} />
    </label>
  );
}
