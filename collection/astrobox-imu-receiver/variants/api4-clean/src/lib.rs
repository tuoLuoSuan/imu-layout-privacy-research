#[cfg(feature = "astrobox")]
mod host { include!(concat!(env!("OUT_DIR"), "/host.rs")); }
#[path = "../../../src/receiver.rs"]
pub mod receiver;
#[path = "../../../src/ui_state.rs"]
pub mod ui_state;
#[path = "../../api4-envelope-adapter/src/telemetry.rs"]
pub mod telemetry;
#[path = "../../api4-envelope-adapter/src/structure.rs"]
mod structure;
#[cfg(test)]
#[path = "../../api4-envelope-adapter/src/telemetry_tests.rs"]
mod telemetry_tests;

#[path = "../../api4-envelope-adapter/src/envelope.rs"]
pub mod envelope;
#[cfg(test)]
#[path = "../../api4-envelope-adapter/src/envelope_tests.rs"]
mod envelope_tests;
