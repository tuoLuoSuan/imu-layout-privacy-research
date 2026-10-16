// One-layer observed-envelope adapter; the original receiver core and ACK remain unchanged.
async fn receive(payload: String) {
    crate::telemetry::update(|d|d.event(&payload));
    render();
    let addr=state().lock().ok().and_then(|s|s.addr.clone());
    let Some(addr)=addr else {crate::telemetry::update(|d|d.step("unregistered"));render();return;};
    if payload.len()>8192 {crate::telemetry::update(|d|d.step("ignored"));render();return;}
    let Some(raw)=crate::envelope::unwrap(&payload,PACKAGE) else {
        crate::telemetry::update(|d|d.step("ignored"));render();return;
    };
    if raw.len()>4096||!raw.contains("S5TX1"){crate::telemetry::update(|d|d.step("ignored"));render();return;}
    let v:serde_json::Value=match serde_json::from_str(&raw){Ok(v)=>v,Err(_)=>{crate::telemetry::update(|d|d.step("ignored"));render();return;}};
    if v.get("p").and_then(|p|p.as_str())==Some("S5TX1"){crate::telemetry::update(|d|d.step("packet"));}
    render();
    let response=match receiver::accept(Path::new(ROOT),&raw){
        Ok(ack)=>{
            crate::telemetry::update(|d|d.step("stored"));
            let complete=ack.part+1==v["n"].as_u64().unwrap_or(0) as usize&&ack.state=="part_complete";
            mutate(|s|s.status=if complete {"已接收并保存，请点保存完整会话到文件；质量待电脑核验".into()}else{format!("正在接收第 {} / {} 段",ack.part+1,v["n"])});
            if complete{refresh_keys();mutate(|s|{if let Some(i)=s.keys.iter().position(|k|k==&ack.token){s.selected=i;}});}
            serde_json::to_string(&ack).unwrap_or_default()
        },
        Err(e)=>{
            crate::telemetry::update(|d|d.step("rejected"));
            mutate(|s|s.status=format!("接收未完成：{e}"));
            serde_json::json!({"p":"S5ERR1","t":v["t"],"s":v["s"],"error":e}).to_string()
        },
    };
    // Show parse/storage success or failure even if the reply host call remains pending.
    render();
    match interconnect::send_qaic_message(addr,PACKAGE.into(),response).await{
        Ok(())=>crate::telemetry::update(|d|d.step("reply_queued")),
        Err(_)=>{crate::telemetry::update(|d|d.step("reply_error"));mutate(|s|s.status="消息已处理，但回复未提交成功；请保留诊断与原记录".into());},
    }
    render();
}
