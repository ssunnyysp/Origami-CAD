import { ModelSelector } from "./ModelSelector";
import { FoldnessSlider } from "./FoldnessSlider";
import { ColorPicker } from "./ColorPicker";
import { ParamSliders } from "./ParamSliders";

export function ControlPanel() {
  return (
    <div className="control-panel">
      <h1>Origami CAD</h1>
      <ModelSelector />
      <FoldnessSlider />
      <ColorPicker />
      <ParamSliders />
    </div>
  );
}
