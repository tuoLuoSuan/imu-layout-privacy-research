#[cfg(feature = "astrobox")]
mod host { include!(concat!(env!("OUT_DIR"), "/host.rs")); }
#[path = "../../../src/receiver.rs"]
pub mod receiver;
#[path = "../../../src/ui_state.rs"]
pub mod ui_state;
pub mod telemetry;
mod structure;
#[cfg(test)]
mod telemetry_tests;

pub mod envelope;
#[cfg(test)]
mod envelope_tests;
