import { ModelSelector } from "./ModelSelector";
import { FoldnessSlider } from "./FoldnessSlider";
import { AnimateToggle } from "./AnimateToggle";
import { ColorPicker } from "./ColorPicker";

export function ControlPanel() {
  return (
    <div className="control-panel">
      <h1>Origami CAD</h1>
      <p className="panel-subtitle">Flasher fold simulator</p>
      <ModelSelector />
      <FoldnessSlider />
      <AnimateToggle />
      <ColorPicker />
    </div>
  );
}
