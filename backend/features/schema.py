"""GuardianX-owned, versioned behavioral-feature schemas."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Mapping, Sequence

V1_FEATURE_ORDER = ("flow_duration", "forward_packet_count", "backward_packet_count", "forward_byte_count", "backward_byte_count", "packet_rate", "byte_rate", "forward_backward_packet_ratio")
V2_FEATURE_ORDER = ("flow_duration", "forward_packet_count", "backward_packet_count", "forward_byte_count", "backward_byte_count", "packet_rate", "byte_rate", "is_one_way_flow")
# Backward-compatible public name for the original locked order.
MVP_FEATURE_ORDER = V1_FEATURE_ORDER

@dataclass(frozen=True)
class GuardianXFeatureSchema:
    name: str = "guardianx_behavioral_features"
    version: str = "v1"
    feature_names: Sequence[str] = field(default_factory=lambda: V1_FEATURE_ORDER)
    descriptions: Mapping[str, str] = field(default_factory=dict)
    def validate(self, values: Mapping[str, object]) -> None:
        missing, extra = set(self.feature_names) - set(values), set(values) - set(self.feature_names)
        if missing or extra: raise ValueError(f"Feature names do not match schema; missing={sorted(missing)}, extra={sorted(extra)}")

_COMMON = {"flow_duration": "Elapsed flow duration in seconds.", "forward_packet_count": "Forward-direction packet count.", "backward_packet_count": "Backward-direction packet count.", "forward_byte_count": "Forward-direction byte count.", "backward_byte_count": "Backward-direction byte count.", "packet_rate": "Total packets per second.", "byte_rate": "Total bytes per second."}
V1_SCHEMA = GuardianXFeatureSchema(feature_names=V1_FEATURE_ORDER, descriptions={**_COMMON, "forward_backward_packet_ratio": "Forward packets divided by backward packets."})
V2_SCHEMA = GuardianXFeatureSchema(version="v2", feature_names=V2_FEATURE_ORDER, descriptions={**_COMMON, "is_one_way_flow": "1 when no backward packet was observed, else 0."})
SCHEMAS = {"v1": V1_SCHEMA, "v2": V2_SCHEMA}
CURRENT_SCHEMA = V1_SCHEMA
APPROVED_SCHEMA = V2_SCHEMA

def get_schema(version: str) -> GuardianXFeatureSchema:
    try: return SCHEMAS[version]
    except KeyError as error: raise ValueError(f"Unsupported GuardianX feature schema version: {version}") from error
