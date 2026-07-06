import { useAppStore } from "../../store/useAppStore";

export function ModelSelector() {
  const presets = useAppStore((s) => s.presets);
  const selectedPresetId = useAppStore((s) => s.selectedPresetId);
  const selectPreset = useAppStore((s) => s.selectPreset);

  return (
    <label className="control-row">
      <span>Model</span>
      <select value={selectedPresetId} onChange={(e) => selectPreset(e.target.value)}>
        {presets.map((preset) => (
          <option key={preset.id} value={preset.id}>
            {preset.name}
          </option>
        ))}
      </select>
    </label>
  );
}
