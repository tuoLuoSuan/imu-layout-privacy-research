#[cfg(feature = "astrobox")]
mod host { include!(concat!(env!("OUT_DIR"), "/host.rs")); }
#[path = "../../../src/receiver.rs"]
pub mod receiver;
#[path = "../../../src/ui_state.rs"]
pub mod ui_state;
pub mod telemetry;
#[cfg(test)]
mod telemetry_tests;
