import unittest
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT.parent) not in sys.path:
    sys.path.insert(0, str(ROOT.parent))
if "engineering_app" not in sys.modules:
    pkg = types.ModuleType("engineering_app")
    pkg.__path__ = [str(ROOT)]
    pkg.__file__ = str(ROOT / "__init__.py")
    sys.modules["engineering_app"] = pkg

from engineering_app.core.pump_sizing import (
    PumpSizingInputs,
    atmospheric_pressure_kpa_abs_from_elevation,
    calculate_pump_sizing,
)


class PumpSizingTests(unittest.TestCase):
    def _base_inputs(self) -> PumpSizingInputs:
        return PumpSizingInputs(
            flow_m3_h=56.781,
            flow_gpm=250.0,
            density_kg_m3=998.0,
            viscosity_cp=1.0,
            liquid_temperature_c=25.0,
            suction_static_head_m=1.52,
            discharge_static_head_m=24.4,
            suction_pipe_length_m=9.14,
            discharge_pipe_length_m=137.2,
            suction_pipe_id_mm=77.9,
            discharge_pipe_id_mm=62.7,
            suction_roughness_mm=0.045,
            discharge_roughness_mm=0.045,
            suction_k_total=4.0,
            discharge_k_total=12.0,
            surface_pressure_kpa_abs=101.325,
            minimum_npsh_margin_ratio=1.2,
            pump_efficiency_fraction=0.75,
            motor_efficiency_fraction=0.93,
            motor_service_factor=1.15,
            required_npshr_m=3.7,
            vapor_pressure_kpa_abs=None,
            curve_shutoff_head_m=45.7,
            curve_max_flow_m3_h=79.5,
            curve_head_at_max_flow_m=21.3,
        )

    def test_calculate_pump_sizing_returns_positive_duty(self):
        result = calculate_pump_sizing(self._base_inputs())
        self.assertGreater(result.required_tdh_m, 0.0)
        self.assertGreater(result.hydraulic_power_kw, 0.0)
        self.assertGreater(result.recommended_motor_kw, 0.0)

    def test_npsh_warning_when_npshr_too_high(self):
        inputs = self._base_inputs()
        inputs.required_npshr_m = 12.0
        result = calculate_pump_sizing(inputs)
        self.assertLess(result.npsh_margin_m, 0.0)
        self.assertTrue(any("below NPSHr" in item for item in result.warnings))

    def test_atmospheric_pressure_decreases_with_elevation(self):
        sea_level = atmospheric_pressure_kpa_abs_from_elevation(0.0)
        mountain = atmospheric_pressure_kpa_abs_from_elevation(2000.0)
        self.assertGreater(sea_level, mountain)


if __name__ == "__main__":
    unittest.main()
