use imus5_receiver::ui_state::{Action, State};

#[test]
fn prepare_is_visible_before_host_work_and_never_claims_ready() {
    let mut s = State::new();
    assert_eq!(s.click("prepare"), Action::Prepare);
    assert!(s.working);
    assert!(s.status.contains("查询"));
    assert!(s.addr.is_none());
    assert_eq!(s.clicks, 1);
}
#[test]
fn repeated_click_cannot_launch_a_second_operation_or_change_selection() {
    let mut s = State::new();
    s.keys = vec!["a".repeat(16), "b".repeat(16)];
    assert_eq!(s.click("prepare"), Action::Prepare);
    assert_eq!(s.click("prepare"), Action::None);
    assert_eq!(s.click("next"), Action::None);
    assert_eq!(s.selected, 0);
    assert!(s.working);
}
#[test]
fn local_probe_is_observable_without_a_device_and_preserves_pending_work() {
    let mut s = State::new();
    assert_eq!(s.click("probe"), Action::Check);
    assert!(s.feedback.contains("界面响应正常"));
    assert!(s.addr.is_none());
    assert!(s.working);
    assert!(!s.status.contains("通过"));
    s.working = false; // The host's async check completes before the next action.
    s.click("prepare");
    let stage = s.status.clone();
    s.click("probe");
    assert_eq!(s.status, stage);
    assert!(s.working);
    assert_eq!(s.clicks, 3);
}
#[test]
fn save_requires_a_completed_session_and_reserves_it_against_switches() {
    let mut s = State::new();
    assert_eq!(s.click("save"), Action::None);
    assert!(!s.working);
    s.keys = vec!["a".repeat(16), "b".repeat(16)];
    s.click("next");
    assert_eq!(s.selected, 1);
    assert_eq!(s.click("save"), Action::Save);
    assert!(s.working);
    assert_eq!(s.click("next"), Action::None);
    assert_eq!(s.selected, 1);
}
