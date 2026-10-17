fn render() {
    let Ok(s)=state().lock() else { return; };
    let Some(id)=s.root_id.clone() else { return; };
    fn secondary(label:&str,id:&str)->ui::Element {
        button(label,id).bg("#E4F1F0").text_color("#176B6D")
    }
    let status=if s.status=="先点界面检查，再准备接收" {
        "连接手表后，点准备接收"
    } else if s.status=="已接收并保存，请点保存完整会话到文件；质量待电脑核验" {
        "已接收并保存，可保存到手机"
    } else { &s.status };
    let selected=if s.keys.is_empty() { "暂无接收记录".to_string() }
        else {format!("记录 {} / {}",s.selected+1,s.keys.len())};
    let mut root=ui::Element::new(ui::ElementType::Div,None)
        .without_default_styles().bg("#F3F6FA").text_color("#102A43")
        .flex().flex_direction(ui::FlexDirection::Column).width_full()
        .min_height(560).padding(20).gap(16)
        .child(ui::Element::new(ui::ElementType::P,Some("IMU 腕部接收"))
            .without_default_styles().size(26).text_color("#102A43"))
        .child(ui::Element::new(ui::ElementType::Div,None)
            .without_default_styles().bg("#FFFFFF").radius(20).padding(20)
            .child(text(status)))
        .child(button(if s.addr.is_some(){"接收已准备"}else{"准备接收"},"prepare"));
    let mut card=ui::Element::new(ui::ElementType::Div,None)
        .without_default_styles().bg("#FFFFFF").radius(20).padding(20)
        .flex().flex_direction(ui::FlexDirection::Column).gap(12)
        .child(text(&selected));
    if !s.keys.is_empty() {
        card=card.child(secondary("下一条记录","next"))
            .child(button("保存文件…","save"));
    }
    root=root.child(card).child(secondary("刷新记录","refresh"))
        .child(text("在手表发送记录，接收完成后保存到手机。"))
        .child(text("v0.2.5").size(12));
    drop(s);
    ui::render(&id,root);
}
