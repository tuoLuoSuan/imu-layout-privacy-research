use wasmtime_wasi::{WasiCtx,WasiCtxBuilder,WasiCtxView,WasiView,FsPerms};
use wasmtime::{AsContextMut,Config,Engine,Store,Result,Error};
use wasmtime::component::{Component,ComponentType,Func,Instance,Lift,Linker,Lower,Resource,ResourceAny,ResourceTable,ResourceType,Val};

#[derive(Clone,Default)]
struct Element {texts:Vec<String>}
struct Context {
    wasi:WasiCtx,
    replies:Vec<String>,
    table:ResourceTable,
    renders:Vec<Vec<String>>,
    queries:u32,
    registrations:u32,
    sends:u32,
    deny:bool,
    block_query:bool,
    reply_deny:bool,
    query_entered:Arc<Notify>,
    query_release:Arc<Notify>,
}
#[derive(ComponentType,Lift,Lower)]
#[component(record)]
struct Device {name:String,addr:String}

fn own_element(s:&mut wasmtime::StoreContextMut<Context>,el:Element)->Result<Val>{
    let r=s.data_mut().table.push(el)?;
    Ok(Val::Resource(ResourceAny::try_from_resource(r,&mut *s)?))
}
fn get_element(s:&mut wasmtime::StoreContextMut<Context>,v:&Val)->Result<(Resource<Element>,Element)>{
    let Val::Resource(r)=v else {return Err(Error::msg("expected UI resource"))};
    let r=r.try_into_resource::<Element>(&mut *s)?;
    let el=s.data().table.get(&r)?.clone();
    Ok((r,el))
}
fn find(instance:Instance,store:&mut Store<Context>,interface:&str,name:&str)->Func{
    let (_,i)=instance.get_export(store.as_context_mut(),None,interface).expect("event interface");
    let (_,f)=instance.get_export(store.as_context_mut(),Some(&i),name).expect("event function");
    instance.get_func(store.as_context_mut(),&f).expect("function")
}

#[tokio::main(flavor="current_thread")]
async fn main()->Result<()> {
    let path=std::env::args().nth(1).ok_or_else(||Error::msg("actual component path required"))?;
    let deny=std::env::args().any(|s|s=="deny");
    let busy=std::env::args().any(|s|s=="busy");
    let v2=std::env::args().any(|s|s=="v2");
    let reply_deny=std::env::args().any(|s|s=="reply-denied");
    let structure_only=std::env::args().any(|s|s=="structure-only");
    let enveloped=std::env::args().any(|s|s=="enveloped");
    let mut cfg=Config::new();cfg.wasm_component_model(true).wasm_component_model_async(true);
    let engine=Engine::new(&cfg)?;
    let component=Component::from_file(&engine,path)?;
    let mut linker=Linker::<Context>::new(&engine);
    linker.allow_shadowing(true);
    wasmtime_wasi::p2::add_to_linker_async(&mut linker)?;
    wasmtime_wasi::p3::add_to_linker(&mut linker)?;
    {
        let mut ui=linker.instance("astrobox:psys-host-v4/ui")?;
        ui.resource("element",ResourceType::host::<Element>(),|mut s,id|{
            s.data_mut().table.delete(Resource::<Element>::new_own(id))?;
            Ok(())
        })?;
        ui.func_new("[constructor]element",|mut s,_,params,results|{
            let mut el=Element::default();
            if let Val::Option(Some(v))=&params[1] {if let Val::String(v)=&**v {el.texts.push(v.clone());}}
            results[0]=own_element(&mut s,el)?;Ok(())
        })?;
        for method in ["without-default-styles","size","text-color","on","bg","padding","radius","flex","flex-direction","width-full","min-height","gap","border","child"] {
            let name=format!("[method]element.{method}");
            ui.func_new(&name,move|mut s,_,params,results|{
                let (_,mut el)=get_element(&mut s,&params[0])?;
                if method=="child" {
                    let (r,child)=get_element(&mut s,&params[1])?;
                    el.texts.extend(child.texts);
                    s.data_mut().table.delete(r)?;
                }
                results[0]=own_element(&mut s,el)?;Ok(())
            })?;
        }
        ui.func_new("render",|mut s,_,params,_|{
            let (r,el)=get_element(&mut s,&params[1])?;
            s.data_mut().renders.push(el.texts);
            s.data_mut().table.delete(r)?;
            Ok(())
        })?;
    }
    linker.instance("astrobox:psys-host-v4/device")?.func_wrap_concurrent("get-connected-device-list",|a,():()|Box::pin(async move{
        let (block,entered,release)=a.with(|mut s|{let c=s.data_mut();(c.block_query,c.query_entered.clone(),c.query_release.clone())});
        if block {entered.notify_one();release.notified().await;}
        tokio::task::yield_now().await;
        a.with(|mut s|s.data_mut().queries+=1);
        Ok((vec![Device{name:"Synthetic S5".into(),addr:"SYNTHETIC".into()}],))
    }))?;
    linker.instance("astrobox:psys-host-v4/register")?.func_wrap_concurrent("register-interconnect-recv",|a,(addr,package):(String,String)|Box::pin(async move{
        assert_eq!(addr,"SYNTHETIC");assert_eq!(package,"org.imuresearch.s5probe");
        tokio::task::yield_now().await;
        let deny=a.with(|mut s|{s.data_mut().registrations+=1;s.data_mut().deny});
        let result=if deny {Err("synthetic permission denied".to_string())} else {Ok(())};
        Ok((result,))
    }))?;
    linker.instance("astrobox:psys-host-v4/interconnect")?.func_wrap_concurrent("send-qaic-message",|a,(addr,package,data):(String,String,String)|Box::pin(async move{
        assert_eq!(addr,"SYNTHETIC");assert_eq!(package,"org.imuresearch.s5probe");
        tokio::task::yield_now().await;
        let rejected=a.with(|mut s|{let c=s.data_mut();c.sends+=1;let denied=c.reply_deny&&data.contains("S5ACK1");c.replies.push(data);denied});
        Ok((if rejected {Err("synthetic reply denied".to_string())}else{Ok(())},))
    }))?;
    {
        let mut dialog=linker.instance("astrobox:psys-host-v4/dialog")?;
        for name in ["save-file-start","save-file-write-chunk","save-file-finish","save-file-abort"]{
            dialog.func_new_concurrent(name,|_,_,_,_|Box::pin(async{Err(Error::msg("System save is outside this receive-only fixture"))}))?;
        }
    }
    let run_root=std::env::args().nth(2).ok_or_else(||Error::msg("fresh synthetic directory required"))?;
    std::fs::create_dir(&run_root)?;
    let mut wasi=WasiCtxBuilder::new();wasi.preopened_dir(&run_root,".",FsPerms::ReadWrite)?;wasi.inherit_stdout();wasi.inherit_stderr();
    let ctx=Context {wasi:wasi.build(),table:ResourceTable::new(),renders:Vec::new(),replies:Vec::new(),queries:0,registrations:0,sends:0,deny,block_query:busy,reply_deny,query_entered:Arc::new(Notify::new()),query_release:Arc::new(Notify::new())};
    let mut store=Store::new(&engine,ctx);
    let instance=linker.instantiate_async(&mut store,&component).await?;
    let render=find(instance,&mut store,"astrobox:psys-plugin-v4/event","on-ui-render");
    let click=find(instance,&mut store,"astrobox:psys-plugin-v4/event","on-ui-event");
    let load=find(instance,&mut store,"astrobox:psys-plugin-v4/lifecycle","on-load");
    let event=find(instance,&mut store,"astrobox:psys-plugin-v4/event","on-event");
    let body=r#"{"schema_version":1,"session_id":"1000_abcdef","rows":[[0,1,2,3,"visible"]]}"#;
    let packet=serde_json::json!({"p":"S5TX1","t":"0123456789abcdef","s":"1000_abcdef","m":"legacy1","i":0,"n":1,"o":0,"l":body.len(),"c":crc32(body.as_bytes()),"d":body}).to_string();
    let files=vec!["s5r_2000_abcdef_head.json","s5r_2000_abcdef_b0000.json","s5r_2000_abcdef_tail.json"];
    let rows:Vec<_>=(0..99).map(|i|serde_json::json!([i,1000+i*20,i as f64/100.0,-2,3,"visible"])).collect();
    let bodies=vec![
        serde_json::json!({"kind":"manifest","schema_version":2,"session_id":"2000_abcdef","files":files}).to_string(),
        serde_json::json!({"kind":"head","schema_version":2,"session_id":"2000_abcdef","started_epoch_ms":1000,"row_fields":["sequence","callback_epoch_ms","x","y","z","page_state"],"metadata":{"app_version":"synthetic-test","sensor":"accelerometer","acceleration_unit":"unknown","time_source":"Date.now_callback_arrival"}}).to_string(),
        serde_json::json!({"kind":"block","schema_version":2,"session_id":"2000_abcdef","index":0,"rows":rows,"events":[]}).to_string(),
        serde_json::json!({"kind":"tail","schema_version":2,"session_id":"2000_abcdef","stopped_epoch_ms":3000,"stop_reason":"duration","count":99,"persisted":99,"blocks":1,"quality":{"warnings":[],"classification":"synthetic_not_device_data"}}).to_string(),
    ];
    let v2_messages:usize=bodies.iter().map(|b|(b.len()+1023)/1024).sum();
    store.run_concurrent(async|a|->Result<()>{
        load.call_concurrent(a,&[],&mut[]).await?;
        for n in 0..64 {
            render.call_concurrent(a,&[Val::String("test-root".into())],&mut[]).await?;
            let mut result=[Val::String(String::new())];
            click.call_concurrent(a,&[Val::String("probe".into()),Val::Enum("CLICK".into()),Val::String(String::new())],&mut result).await?;
            assert!(a.with(|mut s|s.data_mut().renders.last().unwrap().iter().any(|v|v.contains("运行检查通过"))));
            if n%16==0 {println!("actual WASM UI checks completed: {}",n+1);}
        }
        let mut result=[Val::String(String::new())];
        if busy {
            let (entered,release)=a.with(|mut s|{let c=s.data_mut();(c.query_entered.clone(),c.query_release.clone())});
            let first=async {
                let mut r=[Val::String(String::new())];
                click.call_concurrent(a,&[Val::String("prepare".into()),Val::Enum("CLICK".into()),Val::String(String::new())],&mut r).await
            };
            let second=async {
                entered.notified().await;
                let mut r=[Val::String(String::new())];
                let res=click.call_concurrent(a,&[Val::String("prepare".into()),Val::Enum("CLICK".into()),Val::String(String::new())],&mut r).await;
                release.notify_one();
                res
            };
            let (r1,r2)=tokio::join!(first,second);r1?;r2?;
        } else {
            for _ in 0..2 {
                click.call_concurrent(a,&[Val::String("prepare".into()),Val::Enum("CLICK".into()),Val::String(String::new())],&mut result).await?;
            }
        }
        if structure_only {
            // Synthetic envelope only: its field names are NOT a device observation.
            let payload=serde_json::json!({"payload":packet,"device_addr":"private-device","private-field":"private-value"}).to_string();
            for _ in 0..12 {
                event.call_concurrent(a,&[Val::Enum("interconnect-message".into()),Val::String(payload.clone())],&mut result).await?;
            }
            return Ok(());
        }
        event.call_concurrent(a,&[Val::Enum("interconnect-message".into()),Val::String(r#"{"data":{"p":"S5TX1","d":"synthetic ignored object"}}"#.into())],&mut result).await?;
        event.call_concurrent(a,&[Val::Enum("interconnect-message".into()),Val::String(wrap_message(packet.clone(),enveloped))],&mut result).await?;
        event.call_concurrent(a,&[Val::Enum("interconnect-message".into()),Val::String(wrap_message(packet.clone(),enveloped))],&mut result).await?;
        if v2&&!deny&&!reply_deny{
            for (i,body) in bodies.iter().enumerate(){
                for offset in (0..body.len()).step_by(1024){
                    let end=(offset+1024).min(body.len());
                    let packet=serde_json::json!({"p":"S5TX1","t":"f00d0123456789ab","s":"2000_abcdef","m":"v2","i":i,"n":4,"o":offset,"l":body.len(),"c":crc32(body.as_bytes()),"d":&body[offset..end]}).to_string();
                    event.call_concurrent(a,&[Val::Enum("interconnect-message".into()),Val::String(wrap_message(packet,enveloped))],&mut result).await?;
                    let response=a.with(|mut c|c.data_mut().replies.last().unwrap().clone());
                    let ack:serde_json::Value=serde_json::from_str(&response)?;
                    assert_eq!(ack["p"],"S5ACK1");assert_eq!(ack["i"],i);assert_eq!(ack["o"],end);
                }
            }
        }
        Ok(())
    }).await??;
    let ctx=store.data();
    assert!(!ctx.renders.iter().flatten().any(|v|v.contains("界面检查")||v.contains("识别记录包")||v.contains("回复提交 0")||v.contains("最近一步")||v.contains("首次只传")));
    assert!(ctx.renders.iter().flatten().any(|v|v.contains("v0.2.4")));
    if structure_only {
        assert_eq!((ctx.queries,ctx.registrations,ctx.sends),(1,1,2)); // Two prepare clicks, each sends hello.
        assert!(ctx.replies.iter().all(|s|serde_json::from_str::<serde_json::Value>(s).unwrap()["p"]=="S5HELLO1"));
        assert!(!std::path::Path::new(&run_root).join("received").exists());
        let view=ctx.renders.last().unwrap().join("\n");
        assert!(!view.contains("收到消息"));
        assert!(!view.contains("回复提交"));
        assert!(!view.contains("payload=text-json(object{"));
        assert!(!view.contains("p=S5TX1"));
        assert!(!view.contains("private-"));
        println!("PASS actual component receive: unknown synthetic envelope remains ignored; diagnostic counters hidden, daily UI, no record files or replies");
        return Ok(());
    }
    if deny {
        assert_eq!((ctx.queries,ctx.registrations,ctx.sends),(2,2,0));
        assert!(!std::path::Path::new(&run_root).join("received").exists());
        assert!(ctx.renders.iter().flatten().any(|v|v.contains("synthetic permission denied")));
    }else{
        let ack=ctx.replies.last().ok_or_else(||Error::msg("No reply from real component"))?;
        let ack:serde_json::Value=serde_json::from_str(ack)?;
        assert_eq!(ack["p"],"S5ACK1");assert_eq!(ack["state"],"part_complete");
        let persisted=std::fs::read(std::path::Path::new(&run_root).join("received/0123456789abcdef/part_0000.data"))?;
        assert_eq!(persisted,body.as_bytes());
        assert_eq!((ctx.queries,ctx.registrations),(1,1));
        if reply_deny {
            assert!(ctx.renders.last().unwrap().iter().any(|v|v.contains("回复未提交成功")));
            assert!(!ctx.renders.last().unwrap().iter().any(|v|v.contains("回复提交")));
        }else{
            assert!(ctx.renders.last().unwrap().iter().any(|v|v.contains("已接收并保存")));
            if ctx.renders.iter().flatten().any(|v|v.contains("v0.2.3")){
                assert!(ctx.renders.last().unwrap().iter().any(|v|v.contains(&format!("收到消息 {}",3+if v2{v2_messages}else{0}))));
                assert!(ctx.renders.last().unwrap().iter().any(|v|v.contains(&format!("识别记录包 {}",2+if v2{v2_messages}else{0}))));
                assert!(ctx.renders.last().unwrap().iter().any(|v|v.contains(&format!("保存通过 {}",2+if v2{v2_messages}else{0}))));
                assert!(ctx.renders.last().unwrap().iter().any(|v|v.contains(&format!("回复提交 {}",2+if v2{v2_messages}else{0}))));
            }
        }
    }
    if v2{
        for (i,body) in bodies.iter().enumerate(){
            let actual=std::fs::read(std::path::Path::new(&run_root).join(format!("received/f00d0123456789ab/part_{i:04}.data")))?;
            assert_eq!(actual,body.as_bytes());
        }
        println!("V2 four parts, 99 synthetic rows, all raw part bytes equal, fragment ACKs checked");
    }
    println!("PASS actual component receive: 64 UI checks, query/register/prepare, real isolated WASI filesystem, event/repeated-packet ACK, byte-exact synthetic body; deny={deny} busy={busy} reply_deny={reply_deny}");
    Ok(())
}
use std::sync::Arc;
use tokio::sync::Notify;

impl WasiView for Context {fn ctx(&mut self)->WasiCtxView<'_>{WasiCtxView{ctx:&mut self.wasi,table:&mut self.table}}}
fn crc32(bytes:&[u8])->String{let mut c=!0u32;for b in bytes{c^=*b as u32;for _ in 0..8{c=(c>>1)^if c&1!=0{0xedb88320}else{0};}}format!("{:08x}",!c)}
fn wrap_message(raw:String,enveloped:bool)->String{
    if !enveloped{return raw;}
    // Same shape as observed on-device; these outer names/values are synthetic.
    serde_json::json!({"syntheticA":"address","syntheticB":"label","syntheticC":raw,"pkgName":"org.imuresearch.s5probe"}).to_string()
}
