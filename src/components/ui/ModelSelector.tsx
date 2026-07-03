import { PRESETS } from "../../model/presets";
import { useAppStore } from "../../store/useAppStore";

export function ModelSelector() {
  const selectedPresetId = useAppStore((s) => s.selectedPresetId);
  const selectPreset = useAppStore((s) => s.selectPreset);

  return (
    <label className="control-row">
      <span>Model</span>
      <select value={selectedPresetId} onChange={(e) => selectPreset(e.target.value)}>
        {PRESETS.map((preset) => (
          <option key={preset.id} value={preset.id}>
            {preset.name}
          </option>
        ))}
      </select>
    </label>
  );
}
